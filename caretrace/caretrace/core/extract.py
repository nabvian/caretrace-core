"""Extraction layer.

`Extractor` is the modular seam. `RuleExtractor` is the deterministic
implementation shipped with the MVP; an OCR- or LLM-backed extractor can be
substituted by implementing the same interface, and the audit engine
downstream is unaffected because it consumes only the RawItem records below.

Nothing here invents a value. If a pattern does not match, no item is emitted
and the document is reported as extraction-incomplete.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Protocol

from ..packs.medical import lexicon as LX
from . import extract_generic as EG
from . import normalize as N
from .models import DocType


# --------------------------------------------------------------------------
# Raw extraction records (pre-persistence)
# --------------------------------------------------------------------------

@dataclass
class RawItem:
    kind: str                      # OBSERVATION | CLAIM | MEDICATION | REFERENCE | EVENT
    source_text: str
    char_start: int
    char_end: int
    confidence: float = 1.0
    payload: dict = field(default_factory=dict)


class Extractor(Protocol):
    name: str

    def classify(self, full_text: str, filename: str) -> str: ...
    def extract_page(self, page_text: str, doc_type: str,
                     doc_date: Optional[str]) -> list[RawItem]: ...


# --------------------------------------------------------------------------
# Document classification
# --------------------------------------------------------------------------

_CLASSIFIER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (DocType.DISCHARGE_SUMMARY, ("discharge summary", "discharge date")),
    (DocType.MEDICATION_LIST, ("medication list", "current medications",
                               "medications at discharge")),
    (DocType.PRESCRIPTION, ("rx", "prescription")),
    (DocType.LAB_REPORT, ("complete blood count", "laboratory summary",
                          "iron studies", "cumulative laboratory",
                          "reference", "verified by")),
    (DocType.REFERRAL, ("referral", "dear colleague", "thank you for seeing")),
    (DocType.FOLLOWUP, ("follow-up note", "follow up note", "interval history")),
    (DocType.CONSULTATION, ("consultation note", "consultation date",
                            "examination:")),
    (DocType.PATHOLOGY_REPORT, ("histopathology", "biopsy report")),
)


def _classifier_rules() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Core rules plus every cue the active packs declare.

    Document kinds belong to the modality that issues them, so a new pack
    brings its own report headings with it and core stays unchanged.
    """
    rules = list(_CLASSIFIER_RULES)
    for doc_type, phrases in LX.DOCUMENT_CUES.items():
        rules.append((doc_type, phrases))
    return tuple(rules)


def classify_text(full_text: str, filename: str = "") -> str:
    t = full_text.lower()
    scores: dict[str, int] = {}
    for doc_type, keys in _classifier_rules():
        score = sum(3 for k in keys if k in t)
        if score:
            scores[doc_type] = scores.get(doc_type, 0) + score
    # Filename is a weak hint only — never a key, never decisive on its own.
    fname = filename.lower()
    hints = {
        DocType.LAB_REPORT: ("cbc", "lab", "ferritin", "laboratory"),
        DocType.PRESCRIPTION: ("prescription", "rx"),
        DocType.CONSULTATION: ("consultation",),
        DocType.DISCHARGE_SUMMARY: ("discharge",),
        DocType.MEDICATION_LIST: ("medication_list", "medication list", "med_list"),
        DocType.REFERRAL: ("referral",),
        DocType.FOLLOWUP: ("followup", "follow_up", "follow-up"),
    }
    for doc_type, keys in list(hints.items()) + list(LX.FILENAME_CUES.items()):
        if any(k in fname for k in keys):
            scores[doc_type] = scores.get(doc_type, 0) + 2
    if not scores:
        return DocType.OTHER
    return max(scores.items(), key=lambda kv: kv[1])[0]


# --------------------------------------------------------------------------
# Observation extraction
# --------------------------------------------------------------------------

# label ..... value unit
_OBS_RX = re.compile(
    r"^[ \t>*\-]*"
    r"(?P<label>[A-Za-z][A-Za-z ()./%-]{1,44}?)"
    r"\s*[:\-]?\s{1,}"
    r"(?P<value>-?\d+(?:\.\d+)?)"
    r"\s*"
    r"(?P<unit>%|[A-Za-z][A-Za-z^0-9/µ%]{0,12})?"
    r"(?P<rest>.*)$",
    re.M)

# 'Hemoglobin 9.2 g/dL' embedded in a prose sentence
_INLINE_OBS_RX = re.compile(
    r"(?P<label>[A-Za-z][A-Za-z ]{1,28}?)\s*(?:of|:|=|\bwas\b|\bis\b)?\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>g/dL|g/dl|gm/dL|fL|fl|pg|%|ng/mL|ng/ml|mg/dL|mg/dl|"
    r"x10\^\d+/L|x10\^\d+/l)", re.I)

# A leading date on a cumulative-summary row.
_ROW_DATE_RX = re.compile(r"^\s*(\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4})\s{2,}(.*)$")

# Reference-range fragment we must not mistake for a value.
_REF_RANGE_RX = re.compile(r"\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?")

_NON_CONCEPT_LABELS = {
    "page", "report no", "mrn", "reg", "lic", "date", "sample", "case ref",
    "dob", "admission date", "discharge date", "start date", "stop date",
    "list date", "report date", "consultation date", "follow-up date",
}


def _clean_label(raw: str) -> str:
    lab = raw.strip().strip(":-. ")
    lab = re.sub(r"\s+", " ", lab)
    return lab


_DATED_ATTRIB_RX = re.compile(
    r"\bdated\s+(\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4}|\d{4}-\d{2}-\d{2})", re.I)

# '<document noun> dated <date>' — lets a value quoted inside a note be
# attributed to the document it is quoted FROM rather than to the note.
_DOC_NOUN = (r"(?:discharge\s+summary|cbc|complete\s+blood\s+count|"
             r"consultation(?:\s+note)?|prescription|medication\s+list|"
             r"referral(?:\s+letter)?|ferritin\s+report|laboratory\s+summary|"
             r"lab(?:oratory)?\s+report|report)")
_CITED_DOC_RX = re.compile(
    _DOC_NOUN + r"\s+dated\s+(\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.I)
_SENT_SPLIT_RX = re.compile(r"(?<=[.;])\s+|\n")


def _cited_document_dates(page_text: str) -> dict[str, tuple[str, str]]:
    """Map a normalized document noun -> (iso_date, precision) as cited on the page."""
    out: dict[str, tuple[str, str]] = {}
    for m in _CITED_DOC_RX.finditer(page_text):
        noun = re.sub(r"\s+", " ", m.group(0)[:m.group(0).lower().rfind("dated")]).strip().lower()
        iso, prec = N.parse_date(m.group(1))
        if iso:
            out[noun] = (iso, prec)
    return out


def _sentence_at(page_text: str, pos: int) -> str:
    start = max((page_text.rfind(d, 0, pos) for d in (". ", ".\n", ";", "\n")), default=-1)
    start = 0 if start == -1 else start + 1
    m = _SENT_SPLIT_RX.search(page_text, pos)
    end = m.start() if m else len(page_text)
    return page_text[start:end]


def _line_bounds(page_text: str, pos: int) -> tuple[int, int]:
    ls = page_text.rfind("\n", 0, pos) + 1
    le = page_text.find("\n", pos)
    return ls, (len(page_text) if le == -1 else le)


def _attribute_date(page_text: str, line: str, line_start: int, match_pos: int,
                    default_date: Optional[str], default_precision: str
                    ) -> tuple[Optional[str], str, str]:
    """Decide which date an observation belongs to.

    Precedence, strongest first:
      1. a date leading the row itself (cumulative summary transcription)
      2. an explicit '(dated ...)' / 'dated ...' attribution on the same line
      3. the nearest preceding 'dated ...' attribution in the surrounding text
      4. the page/document date
    Returns (iso, precision, basis).
    """
    rowm = _ROW_DATE_RX.match(line)
    if rowm:
        iso, prec = N.parse_date(rowm.group(1))
        if iso:
            return iso, prec, "row"

    same_line = list(_DATED_ATTRIB_RX.finditer(line))
    if same_line:
        iso, prec = N.parse_date(same_line[-1].group(1))
        if iso:
            return iso, prec, "attributed"

    # A value quoted inside a sentence that names another document belongs to
    # THAT document's date, not to the page it is quoted on.
    cited = _cited_document_dates(page_text)
    if cited:
        sentence = _sentence_at(page_text, match_pos).lower()
        hits = [(sentence.rfind(noun), noun) for noun in cited if noun in sentence]
        hits = [h for h in hits if h[0] >= 0]
        if hits:
            _, noun = max(hits)
            iso, prec = cited[noun]
            return iso, prec, "cited"

    # Nearest preceding attribution — take the LAST one before this match.
    ctx_start = max(0, line_start - 240)
    preceding = list(_DATED_ATTRIB_RX.finditer(page_text, ctx_start, match_pos))
    if preceding:
        iso, prec = N.parse_date(preceding[-1].group(1))
        if iso:
            return iso, prec, "attributed"

    return default_date, default_precision, "document"


def extract_observations(page_text: str, default_date: Optional[str],
                         default_precision: str = "day") -> list[RawItem]:
    items: list[RawItem] = []
    seen_spans: set[tuple[int, int, str]] = set()

    def _emit(concept, surface, value, unit, line, ls, le, pos, base_conf,
              extra=None):
        key = (ls, le, concept)
        if key in seen_spans:
            return
        obs_date, precision, basis = _attribute_date(
            page_text, line, ls, pos, default_date, default_precision)
        conf = base_conf
        if basis == "row":
            conf = min(conf, 0.93)   # transcription of an earlier report
        seen_spans.add(key)
        items.append(RawItem(
            kind="OBSERVATION", source_text=line.strip(),
            char_start=ls, char_end=le, confidence=conf,
            payload={"concept": concept, "surface_form": surface, "value": value,
                     "unit": unit, "date": obs_date, "date_precision": precision,
                     "date_basis": basis,
                     **{k: v for k, v in (extra or {}).items() if v is not None}},
        ))

    # Layout-agnostic pass. Measurements are located unit-first by the UCUM
    # grammar and labelled by position (see core.extract_generic), so no
    # laboratory's page format is encoded here. Unrecognised analytes are
    # retained under an `unmapped:` key rather than dropped.
    for g in EG.extract_measurements(page_text):
        concept, display, method = N.resolve_label(g.label)
        if concept is None:
            continue
        # An unrecognised label carrying a plain amount ('Ferrous sulfate
        # 100 mg') is a dose, not an observation of the patient. Medication
        # extraction owns those; asserting them as observations would invent
        # a measurement that no report made.
        if method == "UNRECOGNISED" and g.amount_like:
            continue
        ls, le = g.line_start, g.line_start + len(g.line)
        if N.is_unmapped(concept):
            unit = g.unit_canonical
        else:
            unit = N.normalize_unit(concept, g.unit or None)
        # Confidence reflects how the label was associated, not medical truth.
        conf = g.confidence
        if method == "CONTAINED":
            conf = min(conf, 0.86)      # label read out of running prose
        elif method == "UNRECOGNISED":
            conf = min(conf, 0.72)      # value certain, concept unmapped
        if _ROW_DATE_RX.match(g.line):
            conf = min(conf, 0.93)      # transcription of an earlier report
        _emit(concept, display if method != "UNRECOGNISED" else g.label,
              g.value, unit, g.line, ls, le, g.span[0], conf,
              extra={"label_match": method,
                     "unit_surface": g.unit,
                     "unit_dimension": g.dimension,
                     "reference_range": g.reference_range,
                     "printed_flag": g.flag,
                     "layout": g.layout})

    return items


# --------------------------------------------------------------------------
# Claim extraction
# --------------------------------------------------------------------------

# Sections whose statements are assessments/claims rather than measurements.
_ASSESSMENT_CUES = (
    "assessment", "impression", "diagnosis", "conclusion", "condition at discharge",
)


def extract_claims(page_text: str, default_date: Optional[str],
                   default_precision: str = "day") -> list[RawItem]:
    items: list[RawItem] = []
    lowered = page_text.lower()
    claimed_spans: list[tuple[int, int]] = []

    for ctd in LX.CLAIM_TYPES:
        for pat in ctd.patterns:
            start = 0
            while True:
                idx = lowered.find(pat, start)
                if idx == -1:
                    break
                start = idx + len(pat)
                # Skip if a longer claim already covers this span
                if any(a <= idx < b for a, b in claimed_spans):
                    continue
                line_start = page_text.rfind("\n", 0, idx) + 1
                line_end = page_text.find("\n", idx)
                line_end = len(page_text) if line_end == -1 else line_end
                line = page_text[line_start:line_end].strip()
                if not line:
                    continue
                # A line that merely reports a measured number is not a claim.
                if re.search(r"\b\d+(\.\d+)?\s*(g/dL|fL|pg|ng/mL|mg/dL)\b", line, re.I):
                    if ctd.key not in ("HB_NORMALIZED",):
                        continue
                ctx = page_text[max(0, line_start - 400):line_end].lower()
                in_assessment = any(c in ctx for c in _ASSESSMENT_CUES)
                conf = 0.95 if in_assessment else 0.82
                claimed_spans.append((line_start, line_end))
                items.append(RawItem(
                    kind="CLAIM", source_text=line,
                    char_start=line_start, char_end=line_end, confidence=conf,
                    payload={"claim_text": line.rstrip(". "),
                             "claim_type": ctd.key,
                             "date": default_date,
                             "date_precision": default_precision},
                ))
                break  # one hit per pattern per page is enough
    return items


# --------------------------------------------------------------------------
# Medication extraction
# --------------------------------------------------------------------------

_DOSE_RX = r"(?P<dose>\d+(?:\.\d+)?)\s*(?P<unit>mg|mcg|g|ml|iu|units?)"
_FREQ_TERMS = ("once daily", "twice daily", "three times daily", "at night",
               "as required", "every 8 hours", "every 12 hours", "od", "bd", "tds")
_ROUTE_TERMS = ("oral", "iv", "intravenous", "im", "subcutaneous", "topical")

_MED_LINE_RX = re.compile(
    r"^[ \t]*(?:\d+[.)]\s*)?(?P<name>[A-Za-z][A-Za-z '\-]{2,38}?)\s+" + _DOSE_RX +
    r"(?P<rest>.*)$", re.M | re.I)

# Table-form row: "Folic acid   5 mg   once daily   oral   active"
_MED_TABLE_RX = re.compile(
    r"^[ \t]*(?P<name>[A-Za-z][A-Za-z '\-]{2,38}?)\s{2,}" + _DOSE_RX +
    r"\s{2,}(?P<freq>[A-Za-z ]{2,20}?)\s{2,}(?P<route>[A-Za-z]{2,12})\s{2,}"
    r"(?P<status>[A-Za-z]{3,12})\s*$", re.M | re.I)

_NON_DRUG_NAMES = {"page", "date", "case ref", "reference", "test", "result",
                   "drug", "hemoglobin", "haemoglobin", "mcv", "mch", "mchc",
                   "rdw", "wbc", "rbc", "platelet count", "hematocrit", "hb",
                   "serum ferritin", "serum creatinine", "plt", "tlc", "pcv",
                   "glucose", "ferritin", "creatinine"}


def _med_fields(rest: str) -> dict:
    r = rest.lower()
    freq = next((f for f in _FREQ_TERMS if f in r), None)
    route = next((t for t in _ROUTE_TERMS if re.search(rf"\b{t}\b", r)), None)
    status = None
    if re.search(r"\bstatus\s*[:\-]?\s*active\b", r) or re.search(r"\bactive\b", r):
        status = "ACTIVE"
    elif re.search(r"\bstopped\b|\bdiscontinued\b|\bceased\b", r):
        status = "STOPPED"
    return {"frequency": freq, "route": route, "status": status}


def extract_medications(page_text: str, doc_type: str,
                        default_date: Optional[str]) -> list[RawItem]:
    items: list[RawItem] = []
    seen: set[tuple[str, int]] = set()

    def _emit(name, dose, unit, extra, line, ls, le, conf):
        norm = N.normalize_drug(name)
        if norm in _NON_DRUG_NAMES or len(norm) < 3:
            return
        key = (norm, ls)
        if key in seen:
            return
        seen.add(key)
        # Status default depends on the document's role, not on inference about
        # the patient: a prescription documents an order; a list documents presence.
        status = extra.get("status")
        if status is None:
            status = "ACTIVE" if doc_type in (
                "PRESCRIPTION", "MEDICATION_LIST") else "DOCUMENTED"
        start_date = None
        sm = re.search(r"start date\s*[:\-]?\s*([^\n]{4,30})", line, re.I)
        if sm:
            start_date, _ = N.parse_date(sm.group(1))
        stop_date = None
        pm = re.search(r"stop(?:ped)? date\s*[:\-]?\s*([^\n]{4,30})", line, re.I)
        if pm:
            stop_date, _ = N.parse_date(pm.group(1))
        items.append(RawItem(
            kind="MEDICATION", source_text=line.strip(),
            char_start=ls, char_end=le, confidence=conf,
            payload={"drug_name": name.strip(), "drug_norm": norm,
                     "dose": dose, "unit": unit,
                     "frequency": extra.get("frequency"),
                     "route": extra.get("route"), "status": status,
                     "start_date": start_date, "stop_date": stop_date,
                     "record_date": default_date},
        ))

    for m in _MED_TABLE_RX.finditer(page_text):
        ls = page_text.rfind("\n", 0, m.start()) + 1
        le = page_text.find("\n", m.start())
        le = len(page_text) if le == -1 else le
        line = page_text[ls:le]
        status = m.group("status").upper()
        _emit(m.group("name"), float(m.group("dose")), m.group("unit").lower(),
              {"frequency": m.group("freq").strip(), "route": m.group("route").lower(),
               "status": "ACTIVE" if status.startswith("ACTIV") else status},
              line, ls, le, 0.96)

    for m in _MED_LINE_RX.finditer(page_text):
        ls = page_text.rfind("\n", 0, m.start()) + 1
        le = page_text.find("\n", m.start())
        le = len(page_text) if le == -1 else le
        line = page_text[ls:le]
        # A prescription entry's attributes (Start date / Status) usually sit on
        # indented continuation lines below it. Extend the block over following
        # indented lines only, stopping at the next numbered entry or a rule.
        block_end = le
        cursor = le
        while cursor < len(page_text):
            nls = cursor + 1
            nle = page_text.find("\n", nls)
            nle = len(page_text) if nle == -1 else nle
            nxt = page_text[nls:nle]
            if not nxt.startswith(("    ", "\t")) or not nxt.strip():
                break
            if re.match(r"\s*(?:\d+[.)]|-{5,})", nxt):
                break
            block_end = nle
            cursor = nle
        block = page_text[ls:block_end]
        if any(nd in line.lower() for nd in ("reference", "result", "unit  ")):
            continue
        _emit(m.group("name"), float(m.group("dose")), m.group("unit").lower(),
              _med_fields(block), block, ls, le, 0.94)

    return items


# --------------------------------------------------------------------------
# Referenced documents and follow-up events
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Qualitative findings (status statements)
# --------------------------------------------------------------------------
#
# Imaging, ECG, EEG and molecular reports state most of their result as text:
# 'no acute infarct', 'sinus rhythm', 'EGFR mutation not detected'. Those are
# documented findings with exactly the audit properties of a numeric result --
# they recur across documents, they change over time, and two documents can
# state opposites. So they are extracted as facts carrying a text value, not
# dropped because they are not numbers.
#
# Only phrases the active packs declare are recognised. Nothing is inferred:
# an unlisted sentence produces nothing rather than a guessed finding.

# A finding must not be captured out of a negated or hypothetical frame
# ('if consolidation develops', 'to exclude infarct') -- those are not
# statements that the finding was observed.
_HYPOTHETICAL_RX = re.compile(
    r"\b(?:if|should|unless|to (?:exclude|rule out|assess for)|"
    r"query|\?|consider|suspected|possible|cannot exclude|"
    r"r/o|rule out|advise|recommend(?:ed)?|plan(?:ned)?\s+for|"
    r"awaiting|pending)\b", re.I)


# A negator immediately before a phrase inverts it. 'No acute infarct' must
# never be recorded as 'acute infarct'; the packs list both polarities, so the
# correct move is to reject the positive match and let the negative phrase win.
_NEGATOR_RX = re.compile(
    r"\b(?:no|not|non|without|negative for|free of|absent|denies|"
    r"unremarkable for|ruled out)\s*$", re.I)

# A generic result word only counts next to a label: 'HBV DNA: Detected'.
_ANCHOR_RX = re.compile(r"[:\-\u2013\u2014|\t]\s*$")


def _negated(low: str, pos: int) -> bool:
    """Is the phrase at pos immediately preceded by a negator?"""
    return bool(_NEGATOR_RX.search(low[max(0, pos - 24):pos]))


def extract_findings(page_text: str, default_date: Optional[str],
                     precision: str = "day") -> list[RawItem]:
    """Extract documented qualitative findings declared by the active packs."""
    items: list[RawItem] = []
    offset = 0
    for line in page_text.split("\n"):
        ls, le = offset, offset + len(line)
        offset = le + 1
        low = line.lower()
        if not low.strip():
            continue
        hypothetical = bool(_HYPOTHETICAL_RX.search(low))
        # Character spans already consumed on this line, so one finding can
        # never be re-read as a shorter, more generic one.
        taken: list[tuple[int, int]] = []
        for phrase_low, concept, value_key, phrase in LX.STATUS_PHRASES:
            start = 0
            while True:
                pos = low.find(phrase_low, start)
                if pos < 0:
                    break
                end = pos + len(phrase_low)
                start = end
                # Word boundaries: 'ct' must not match inside 'contract'.
                before = low[pos - 1] if pos else " "
                after = low[end] if end < len(low) else " "
                if before.isalnum() or after.isalnum():
                    continue
                if any(pos < b and e < end + 1 and e > pos for b, e in taken) or \
                        any(b <= pos < e or b < end <= e for b, e in taken):
                    continue
                if phrase_low in LX.ANCHORED_PHRASES and \
                        not _ANCHOR_RX.search(low[:pos]):
                    continue
                # A positive phrase inside a negation is the negation's subject,
                # not a documented positive finding. Polarity comes from the
                # pack's declared value class, not from guessing at the wording.
                if LX.status_value_positive(concept, value_key) and _negated(low, pos):
                    continue
                taken.append((pos, end))
                if hypothetical:
                    # Seen but not asserted: the reviewer can still find the
                    # sentence, but CARETRACE will not report it as documented.
                    continue
                items.append(RawItem(
                    kind="FINDING", source_text=line.strip(),
                    char_start=ls, char_end=le, confidence=0.92,
                    payload={
                        "concept": concept,
                        "surface_form": line[pos:end].strip(),
                        # value_key is what the conflict engine compares;
                        # value_text preserves how the report worded it.
                        "value_key": value_key,
                        "value_text": LX.status_value_label(concept, value_key),
                        "source_phrase": phrase,
                        "date": default_date,
                        "date_precision": precision,
                        "modality": LX.modality_of(concept),
                    },
                ))
    return items


def _flatten(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs to single spaces, keeping a map back to source.

    A phrase in a report is often broken by the page layout -- "CT findings as\n
    described in the CT report" is one sentence that a line break splits. A
    pattern written the way a human writes the phrase then fails to match, so
    matching is done on a flattened view and every reported offset is mapped
    back through `index_map` to the real position in the page text. Provenance
    therefore still points at the original characters.
    """
    out: list[str] = []
    index_map: list[int] = []
    prev_ws = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if not prev_ws and out:
                out.append(" ")
                index_map.append(i)
            prev_ws = True
        else:
            out.append(ch)
            index_map.append(i)
            prev_ws = False
    return "".join(out), index_map


def _line_span(text: str, pos: int) -> tuple[int, int]:
    """Bounds of the line containing `pos`."""
    ls = text.rfind("\n", 0, pos) + 1
    le = text.find("\n", pos)
    return ls, (len(text) if le == -1 else le)


def extract_references(page_text: str) -> list[RawItem]:
    items: list[RawItem] = []
    seen: set[str] = set()
    flat, imap = _flatten(page_text)
    for pattern, label, hint in LX.DOCUMENT_REFERENCE_PATTERNS:
        m = re.search(pattern, flat, re.I)
        if not m or label in seen:
            continue
        seen.add(label)
        start = imap[m.start()] if m.start() < len(imap) else 0
        ls, le = _line_span(page_text, start)
        items.append(RawItem(
            kind="REFERENCE", source_text=page_text[ls:le].strip(),
            char_start=ls, char_end=le, confidence=0.95,
            payload={"label": label, "doc_type_hint": hint},
        ))
    return items


def extract_followup_events(page_text: str, default_date: Optional[str]) -> list[RawItem]:
    items: list[RawItem] = []
    flat, imap = _flatten(page_text)
    for pattern, label in LX.FOLLOWUP_PATTERNS:
        m = re.search(pattern, flat, re.I)
        if not m:
            continue
        start = imap[m.start()] if m.start() < len(imap) else 0
        ls, le = _line_span(page_text, start)
        items.append(RawItem(
            kind="EVENT", source_text=page_text[ls:le].strip(),
            char_start=ls, char_end=le, confidence=0.9,
            payload={"event_type": "EXPECTED_FOLLOWUP", "label": label,
                     "date": default_date, "detail": m.group(0).strip()},
        ))
    return items


# --------------------------------------------------------------------------
# The shipped extractor
# --------------------------------------------------------------------------

class RuleExtractor:
    """Deterministic pattern/lexicon extractor. No model calls."""

    name = "rule-extractor/1.0"

    def classify(self, full_text: str, filename: str) -> str:
        return classify_text(full_text, filename)

    def document_date(self, full_text: str) -> tuple[Optional[str], str]:
        iso, prec, _labelled = N.find_document_date(full_text)
        return iso, prec

    def extract_page(self, page_text: str, doc_type: str,
                     doc_date: Optional[str]) -> list[RawItem]:
        # Only an explicitly LABELLED page date may override the document date.
        # An unlabelled first-date-on-the-page is frequently a date being cited
        # (e.g. '(dated 12 April 2026)'), not the date of the page itself.
        page_date, precision, labelled = N.find_document_date(page_text)
        if labelled and page_date:
            effective, prec = page_date, precision
        else:
            effective, prec = doc_date, "day"
        out: list[RawItem] = []
        out += extract_observations(page_text, effective, prec)
        out += extract_claims(page_text, effective, prec)
        out += extract_medications(page_text, doc_type, effective)
        out += extract_findings(page_text, effective, prec)
        out += extract_references(page_text)
        out += extract_followup_events(page_text, effective)
        return out
