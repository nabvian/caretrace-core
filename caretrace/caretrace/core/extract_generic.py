"""Layout-agnostic extraction.

The requirement this answers: every laboratory and imaging centre formats its
reports differently, so a parser wired to any particular layout cannot scale.
Nothing here encodes a template, a vendor, or a page geometry.

How it works instead -- three layout-independent structural signals:

1. MEASUREMENTS are found unit-first (see core.units). A UCUM-derived grammar
   recognises the unit token; the adjacent number is the candidate value; the
   analyte label is then associated by POSITION, not by matching a known name.
   So an analyte the vocabulary has never seen still yields a measurement,
   flagged as an unrecognised concept rather than dropped.

2. The LABEL is associated geometrically. Reports put the label either to the
   left of the value on the same line (row layout) or above it in a column
   header (columnar layout). Both are detected from whitespace structure: a
   line whose numeric fields align vertically with a header line's fields is a
   column layout; otherwise the text left of the value on its own line is the
   label. Reference ranges are identified as ranges and never read as values.

3. NARRATIVE sections are segmented by heading SHAPE, not heading text: a
   short line, in caps or title case, optionally colon-terminated, followed by
   longer prose lines. That shape holds across institutions. Headings are then
   mapped to canonical roles (indication / technique / findings / impression /
   conclusion) by keyword, and an unmapped heading is preserved verbatim as an
   OTHER section rather than discarded.

Every candidate carries the character span it came from, so provenance holds
regardless of which signal produced it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from . import units as U

# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


@dataclass
class Measurement:
    """One numeric measurement with its layout-derived label."""
    label: str                       # surface label, verbatim
    value: float
    unit: str                        # surface unit, verbatim
    unit_canonical: str
    dimension: Optional[str]
    line: str                        # the whole source line, for provenance
    line_start: int                  # offset of the line in the page text
    span: tuple[int, int]            # value+unit span within the page text
    label_span: Optional[tuple[int, int]] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None       # H / L / abnormal marker as printed
    layout: str = "ROW"              # ROW | COLUMN | INLINE
    confidence: float = 0.9
    row_date: Optional[str] = None    # leading date cell, if the row carried one

    @property
    def source_text(self) -> str:
        return self.line.strip()

    @property
    def amount_like(self) -> bool:
        """Whether the unit denotes a plain amount rather than a concentration.

        A prescription's '100 mg' and a laboratory result's '9.2 g/dL' are both
        measurements, but only the second is an observation of the patient. The
        discriminator that holds across layouts is the unit's dimension: an
        amount with no denominator is a dose or a quantity, whereas a result is
        normally per-volume or dimensionless. Callers combine this with whether
        the label resolved, so genuine analytes reported in bare units (MCV in
        fL, MCH in pg) are unaffected.
        """
        d = self.dimension or ""
        return "_per_" not in d and d in {
            "mass", "volume", "amount", "arbitrary", "count", "catalytic"}


@dataclass
class Section:
    """A narrative section located by heading shape."""
    role: str                        # canonical role, or OTHER
    heading: str                     # heading as printed
    text: str
    start: int
    end: int


# ---------------------------------------------------------------------------
# Layout-independent line analysis
# ---------------------------------------------------------------------------

# A printed reference interval, in any of the common spellings. Recognised so
# its numbers are never mistaken for a result.
REF_RANGE_RX = re.compile(
    r"(?P<range>"
    r"\(?\s*(?:ref(?:erence)?(?:\s*(?:range|interval|value)s?)?\s*[:=]?\s*)?"
    r"(?:-?\d+(?:\.\d+)?\s*(?:-|--|–|—|to)\s*-?\d+(?:\.\d+)?"
    r"|[<>≤≥]\s*-?\d+(?:\.\d+)?)"
    r"\s*\)?)", re.I)

# An abnormality flag as printed beside a result.
FLAG_RX = re.compile(r"(?<![A-Za-z])(H{1,2}|L{1,2}|HIGH|LOW|ABN(?:ORMAL)?|"
                     r"CRIT(?:ICAL)?|\*)(?![A-Za-z])")

# Labels that are document furniture, never analytes. Kept deliberately short:
# this is a structural exclusion list, not a clinical vocabulary.
FURNITURE = {
    "page", "report", "report no", "report number", "reg no", "mrn", "uhid",
    "date", "dated", "sample", "specimen", "collected", "received", "reported",
    "age", "sex", "gender", "dob", "patient", "name", "ref by", "referred by",
    "doctor", "physician", "consultant", "technician", "lab", "laboratory",
    "address", "phone", "tel", "email", "invoice", "bill", "barcode",
    "accession", "case ref", "case", "visit", "encounter", "admission",
    "discharge", "start date", "stop date", "list date", "report date",
    "printed", "signature", "verified by", "authorised by", "authorized by",
    "method", "instrument", "analyser", "analyzer", "units", "unit",
    "reference", "reference range", "normal range", "range", "result",
    "results", "value", "flag", "comment", "comments", "interpretation",
    "test", "tests", "investigation", "investigations", "parameter",
}

_LABEL_TRIM_RX = re.compile(r"^[\s\-*>•\u2022\|]+|[\s:\-=\.]+$")
_SERIAL_RX = re.compile(r"^\d{1,3}[).]\s*")


def clean_label(raw: str) -> str:
    """Strip list bullets, serial numbers and separators; keep the wording."""
    lab = _LABEL_TRIM_RX.sub("", raw or "")
    lab = _SERIAL_RX.sub("", lab)
    lab = re.sub(r"\s{2,}", " ", lab).strip(" :-=.\t|")
    return lab


# Single tokens that make a label furniture whatever they are combined with.
FURNITURE_TOKENS = {
    "page", "mrn", "uhid", "reg", "barcode", "accession", "invoice", "bill",
    "signature", "technician", "physician", "consultant", "address", "phone",
    "tel", "email", "printed", "analyser", "analyzer", "instrument",
}


def is_furniture(label: str) -> bool:
    key = re.sub(r"[^a-z ]", "", (label or "").lower()).strip()
    key = re.sub(r"\s{2,}", " ", key)
    if not key or key in FURNITURE:
        return True
    toks = [t for t in key.split() if t]
    # 'Sample Collected', 'Report Date', 'Verified By' -- composites built
    # entirely from furniture words are furniture too, without listing each
    # combination a laboratory might print.
    if toks and all(t in FURNITURE or t in FURNITURE_TOKENS
                    or t in {"by", "on", "at", "no", "number", "id", "of"}
                    for t in toks):
        return True
    if any(t in FURNITURE_TOKENS for t in toks):
        return True
    # A label that is only a date, a code or a single letter is not an analyte.
    if len(key) < 2 or re.fullmatch(r"[a-z]", key):
        return True
    return False


def line_bounds(text: str, pos: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return start, (len(text) if end == -1 else end)


def _column_starts(line: str) -> list[int]:
    """Column start offsets, from runs of 2+ spaces -- the only reliable
    layout signal available in extracted text."""
    if not line.strip():
        return []
    starts, i = [], 0
    for m in re.finditer(r"(?:^|\s{2,})(\S)", line):
        starts.append(m.start(1))
    return starts


def _header_label_for(header: str, col: int, tol: int = 6) -> Optional[str]:
    """The header cell whose column best aligns with offset `col`."""
    cells = [(m.start(1), m.group(1).strip())
             for m in re.finditer(r"(?:^|\s{2,})(\S(?:[^\s]|\s(?!\s))*)", header)]
    if not cells:
        return None
    best, best_d = None, 10 ** 9
    for start, txt in cells:
        d = abs(start - col)
        if d < best_d:
            best, best_d = txt, d
    return best if best_d <= tol else None


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------


_CELL_SPLIT_RX = re.compile(r"\s{2,}|\t+|\s*\|\s*")


def _cells(line: str) -> list[tuple[int, str]]:
    """(offset, text) cells of a line, split on 2+ spaces, tabs or pipes."""
    out, pos = [], 0
    for part in _CELL_SPLIT_RX.split(line):
        idx = line.find(part, pos)
        if part.strip():
            out.append((idx, part.strip()))
        pos = idx + len(part)
    return out


_BARE_NUM_RX = re.compile(r"^-?\d{1,7}(?:[.,]\d{1,4})?$")

# A date in any of the spellings reports use. Recognised structurally so a
# cumulative-summary row ('18 Jan 2026  Hemoglobin  9.2  g/dL') is labelled
# with the analyte and dated from the row, not labelled with the date.
_DATE_CELL_RX = re.compile(
    r"^(?:\d{1,2}[-/\s](?:\d{1,2}|[A-Za-z]{3,9})\.?[-/\s]\d{2,4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})$")


def _is_date_cell(text: str) -> bool:
    return bool(_DATE_CELL_RX.match((text or "").strip().rstrip(",")))


def extract_cellwise(page_text: str) -> list[Measurement]:
    """Measurements whose value and unit sit in SEPARATE columns.

    Columnar reports print 'Haemoglobin | 9.2 | g/dL | 13.0-17.0'. Adjacency
    fails there, so the row is read as cells: a cell that is a bare unit, a
    cell that is a bare number, and the leftmost text cell as the label. This
    still encodes no template -- only that a table has columns.
    """
    out: list[Measurement] = []
    pos = 0
    for line in page_text.split("\n"):
        ls, pos = pos, pos + len(line) + 1
        cells = _cells(line)
        if len(cells) < 3:
            continue
        unit_cell = next(((o, c) for o, c in cells
                          if U.is_plausible_unit(c)
                          and U.dimension(c) is not None), None)
        if unit_cell is None:
            continue
        num_cells = [(o, c) for o, c in cells if _BARE_NUM_RX.match(c)]
        if not num_cells:
            continue
        # The value is the numeric cell closest to the left of the unit cell;
        # a range cell is not bare-numeric so it cannot be picked here.
        before = [(o, c) for o, c in num_cells if o < unit_cell[0]]
        if not before:
            continue
        v_off, v_txt = before[-1]
        text_cells = [(o, c) for o, c in cells
                      if not _BARE_NUM_RX.match(c) and o < v_off
                      and not U.is_plausible_unit(c)]
        row_date = next((c for _o, c in text_cells if _is_date_cell(c)), None)
        text_cells = [(o, c) for o, c in text_cells if not _is_date_cell(c)]
        if not text_cells:
            continue
        label = clean_label(text_cells[0][1])
        if not label or is_furniture(label):
            continue
        rng = None
        rm = REF_RANGE_RX.search(line[unit_cell[0] + len(unit_cell[1]):])
        if rm:
            rng = rm.group("range").strip()
        try:
            value = float(v_txt.replace(",", "."))
        except ValueError:
            continue
        out.append(Measurement(
            label=label, value=value, unit=unit_cell[1],
            unit_canonical=U.canonical(unit_cell[1]),
            dimension=U.dimension(unit_cell[1]),
            line=line, line_start=ls,
            span=(ls + v_off, ls + unit_cell[0] + len(unit_cell[1])),
            reference_range=rng, flag=None, layout="COLUMN",
            confidence=0.88, row_date=row_date))
    return out


def extract_measurements(page_text: str) -> list[Measurement]:
    """Every measurement on the page, found unit-first and labelled by position."""
    out: list[Measurement] = []
    seen: set[tuple[int, int]] = set()

    for m in U.find_measurements(page_text):
        v_start, v_end = m["value_span"]
        u_start, u_end = m["unit_span"]
        ls, le = line_bounds(page_text, v_start)
        line = page_text[ls:le]

        # A value inside a printed reference range is a range bound, not a
        # result. Check by position so no layout assumption is needed.
        rel_v = v_start - ls
        ranges = [(r.start("range"), r.end("range"))
                  for r in REF_RANGE_RX.finditer(line)]
        in_range = any(a <= rel_v < b for a, b in ranges)
        if in_range:
            continue
        if (v_start, u_end) in seen:
            continue

        left = line[:rel_v]
        # Several measurements can share one line ("Hb: 9.2 g/dL | MCV: 68 fL").
        # The label is what follows the LAST delimiter or preceding unit, not
        # the whole left-hand side.
        row_date = None
        dm = re.match(r"\s*(\S.*?\S)\s{2,}", line)
        if dm and _is_date_cell(dm.group(1)):
            row_date = dm.group(1).strip()
        cut = 0
        for d in ("|", ";", ",", "\u2022", "  "):
            cut = max(cut, left.rfind(d) + len(d) if left.rfind(d) >= 0 else 0)
        for pm in U.find_units(left):
            cut = max(cut, pm[1])
        label = clean_label(left[cut:]) or clean_label(left)
        if _is_date_cell(label):
            # The date is the row's date; the analyte is the next cell along.
            row_date = row_date or label
            nxt = re.match(r"\s*\S(?:[^\s]|\s(?!\s))*\s{2,}(\S(?:[^\s]|\s(?!\s))*)",
                           left)
            label = clean_label(nxt.group(1)) if nxt else ""
        layout = "ROW"

        # No label to the left on this line -> the label may be a column
        # header above. Walk up to the nearest non-blank line that has no
        # measurement of its own and try to align columns with it.
        if not label or is_furniture(label):
            header, hdr_line = None, None
            probe = ls
            for _ in range(4):
                if probe <= 0:
                    break
                p_ls, p_le = line_bounds(page_text, probe - 1)
                cand = page_text[p_ls:p_le]
                probe = p_ls
                if not cand.strip():
                    continue
                if U.find_measurements(cand):
                    continue          # another data row, not a header
                hdr_line = cand
                break
            if hdr_line:
                header = _header_label_for(hdr_line, rel_v)
                # A header aligned over the VALUE column names the value
                # ("Result"), not the analyte. The analyte is then the
                # leftmost cell of the data row.
                if header and is_furniture(clean_label(header)):
                    first = re.match(r"\s*(\S(?:[^\s]|\s(?!\s))*)", line)
                    if first:
                        label, layout = clean_label(first.group(1)), "COLUMN"
                elif header:
                    label, layout = clean_label(header), "COLUMN"

        # Still nothing usable: keep the measurement, name it honestly.
        if not label or is_furniture(label):
            first = re.match(r"\s*(\S(?:[^\s]|\s(?!\s))*)", line)
            cand = clean_label(first.group(1)) if first else ""
            label = cand if cand and not is_furniture(cand) else ""
            layout = "INLINE" if not label else layout

        rng = None
        for a, b in ranges:
            rng = line[a:b].strip()
            break
        fl = None
        tail = line[rel_v + (u_end - v_start):]
        fm = FLAG_RX.search(tail[:14])
        if fm:
            fl = fm.group(1)

        conf = 0.92 if label else 0.55
        if layout == "COLUMN":
            conf = 0.85
        if rng:
            conf = min(0.97, conf + 0.04)   # a printed range corroborates

        seen.add((v_start, u_end))
        out.append(Measurement(
            label=label, value=m["value"], unit=m["unit"],
            unit_canonical=m["unit_canonical"], dimension=m["dimension"],
            line=line, line_start=ls, span=(v_start, u_end),
            label_span=None, reference_range=rng, flag=fl,
            layout=layout, confidence=conf, row_date=row_date))

    # Second pass for rows whose unit sits in its own column, which adjacency
    # cannot see. Lines already covered above are skipped, so no duplicates.
    covered = {m.line_start for m in out}
    for m in extract_cellwise(page_text):
        if m.line_start not in covered:
            out.append(m)
    out.sort(key=lambda x: x.span[0])
    return out


# ---------------------------------------------------------------------------
# Narrative sections, located by heading SHAPE
# ---------------------------------------------------------------------------

ROLE_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("INDICATION",  ("indication", "clinical history", "history", "reason",
                     "clinical details", "referred for", "complaint")),
    ("TECHNIQUE",   ("technique", "protocol", "procedure", "method",
                     "sequences", "contrast", "acquisition", "study")),
    ("COMPARISON",  ("comparison", "prior study", "previous study")),
    ("FINDINGS",    ("findings", "observation", "observations", "description",
                     "report", "examination", "gross", "microscopy")),
    ("IMPRESSION",  ("impression", "conclusion", "opinion", "summary",
                     "interpretation", "diagnosis", "assessment")),
    ("RECOMMENDATION", ("recommendation", "advice", "plan", "follow up",
                        "follow-up", "suggestion")),
)

# Heading SHAPE: a short line, not sentence-like, optionally colon-terminated.
_HEADING_MAX_WORDS = 7
_HEADING_MAX_CHARS = 60


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > _HEADING_MAX_CHARS:
        return False
    body = s.rstrip(":").strip()
    if not body or len(body.split()) > _HEADING_MAX_WORDS:
        return False
    if body[0].isdigit() and not s.endswith(":"):
        return False
    if U.find_measurements(s):
        return False                      # a data row, not a heading
    if s.endswith("."):
        return False                      # a sentence
    is_caps = body.upper() == body and any(c.isalpha() for c in body)
    is_title = all(w[:1].isupper() or not w[:1].isalpha()
                   for w in body.split())
    return bool(s.endswith(":") or is_caps or is_title)


def _role_for(heading: str) -> str:
    h = heading.lower().strip(": ")
    for role, cues in ROLE_CUES:
        if any(c in h for c in cues):
            return role
    return "OTHER"


def extract_sections(page_text: str) -> list[Section]:
    """Segment narrative text by heading shape, preserving unmapped headings."""
    lines: list[tuple[int, str]] = []
    pos = 0
    for ln in page_text.split("\n"):
        lines.append((pos, ln))
        pos += len(ln) + 1

    heads = [(i, off, ln) for i, (off, ln) in enumerate(lines)
             if _is_heading(ln)]
    # A heading needs body text after it, or it is just a short line.
    out: list[Section] = []
    for n, (i, off, ln) in enumerate(heads):
        body_start = off + len(ln) + 1
        stop = len(page_text)
        for j, off2, _ln2 in heads[n + 1:]:
            if j > i:
                stop = off2
                break
        body = page_text[body_start:stop].strip("\n")
        if not body.strip():
            continue
        if len(body.split()) < 2:
            continue
        out.append(Section(role=_role_for(ln), heading=ln.strip().rstrip(":"),
                           text=body, start=body_start, end=stop))
    return out


def section_map(page_text: str) -> dict[str, str]:
    """Canonical role -> text, for packs that want a single lookup."""
    m: dict[str, str] = {}
    for s in extract_sections(page_text):
        if s.role != "OTHER":
            m.setdefault(s.role, s.text)
    return m
