"""Evidence gap detection.

Four gap families, all phrased as statements about the RECORD:

  UNSUPPORTED_CLAIM     a claim whose required evidence is not in the records
  MISSING_DOCUMENT      a document cited by an uploaded record but not uploaded
  MEDICATION_GAP        a medication that cannot be reconciled across records
  MISSING_FOLLOWUP      a documented expected follow-up with no later record

Every gap says what was looked for and what was found. None says the claim is
false or that the care was wrong.
"""
from __future__ import annotations

import re

from datetime import date, timedelta
from typing import Optional, Callable

from ..models import (Claim, ClaimEvidenceStatus, Document, DocumentReference,
                      DocType, EvidenceGap, Event, GapType, Medication, Status)
from ...packs.medical import lexicon as LX


def _d(iso: Optional[str]) -> Optional[date]:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None


def gaps_from_claims(claim_results: list[dict]) -> list[EvidenceGap]:
    """A claim whose declared supporting evidence is not in the records."""
    out: list[EvidenceGap] = []
    for res in claim_results:
        if res["status"] != ClaimEvidenceStatus.NO_LOCATED_EVIDENCE:
            continue
        claim: Claim = res["claim"]
        # If a required test IS in the records but outside the claim's window,
        # say so. Otherwise a reviewer who has seen that result elsewhere reads
        # the gap as an extraction failure rather than a dating problem.
        # The same observation is often restated across several documents; that
        # is one dating problem to report, not one per restatement.
        seen: dict[tuple, str] = {}
        for o in res.get("out_of_window", []):
            seen.setdefault((o["concept"], o["value"], o["obs_date"]), o["explanation"])
        oow = "".join(" " + s for s in seen.values())
        out.append(EvidenceGap(
            case_id=claim.case_id,
            display_id="",  # assigned by the pipeline
            gap_type=GapType.MISSING_SUPPORTING_TEST,
            subject_type="claim",
            title=claim.claim_text,
            basis=("The active pack declares evidence for this claim type. No "
                   "qualifying observation was located in the uploaded records "
                   f"within {res['lookback_days']} days before the claim date. "
                   "This is a statement about the records, not about the claim."
                   + oow),
            status=Status.MISSING,
            subject_id=claim.id,
            evidence_located=[LX.concept_label(c) for c in res["located_concepts"]],
            evidence_not_located=res["missing_labels"],
        ))
    return out


# How far back a citation may reach for the document it refers to. A discharge
# summary citing "the CT report" means a study from this admission, not one from
# six months ago; without a bound, any same-modality document ever uploaded
# would silently satisfy the citation and a real documentation gap would vanish.
REFERENCE_LOOKBACK_DAYS = 45


def _days_between(a: Optional[str], b: Optional[str]) -> Optional[int]:
    if not a or not b:
        return None
    try:
        da = date.fromisoformat(a[:10])
        db = date.fromisoformat(b[:10])
    except ValueError:
        return None
    return (da - db).days


# Words in a citation label that identify the DOCUMENT KIND rather than the
# study. Stripping them leaves the discriminating term ('CT report' -> 'ct'),
# which is what tells a cited CT apart from an MRI when both classify as
# imaging.
_LABEL_STOPWORDS = {"report", "reports", "study", "studies", "scan", "scans",
                    "the", "a", "an", "prior", "previous", "results", "result"}


def _label_terms(label: str) -> list[str]:
    """Discriminating terms of a citation label, longest first."""
    words = re.findall(r"[a-z0-9-]+", label.lower())
    return sorted((w for w in words if w not in _LABEL_STOPWORDS),
                  key=len, reverse=True)


def _mentions(text: str, term: str) -> bool:
    """Whole-word containment.

    Substring matching is unusable here: the two-letter term 'ct' occurs inside
    'acute', 'detected' and 'structures', which would let any radiology report
    satisfy a citation of a CT.
    """
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])",
                     text) is not None


def gaps_from_references(
        references: list[DocumentReference],
        documents: list[Document],
        citing_date_of: Optional[Callable[[DocumentReference],
                                          Optional[str]]] = None,
        citing_document_of: Optional[Callable[[DocumentReference],
                                              Optional[str]]] = None,
        document_terms_of: Optional[Callable[[Document], str]] = None,
) -> tuple[list[EvidenceGap], list[tuple[str, str]]]:
    """A record cites another document; check whether that document was uploaded.

    A citation is satisfied only by a document that is all three of:

      * of the cited KIND -- and specifically the cited study. 'CT report' and
        'MRI report' both classify as imaging, so class alone is too coarse:
        the discriminating term from the label must appear in the candidate.
      * dated within REFERENCE_LOOKBACK_DAYS of the citing record. A discharge
        summary citing 'the CT report' means a study from this admission, not
        one from six months ago.
      * not the citing document itself. A CT report describing its own findings
        is not evidence that a separate cited CT exists.

    Relaxing any of the three would let an unrelated document silently answer
    the citation, erasing exactly the gap this engine exists to expose.

    Returns the gaps plus the resolutions made, as (reference_id, document_id),
    so provenance records which document answered which citation.
    """
    out: list[EvidenceGap] = []
    resolved: list[tuple[str, str]] = []
    uploaded_names = " ".join(d.filename.lower() for d in documents)
    seen: set[tuple[str, Optional[str]]] = set()

    def _terms(d: Document) -> str:
        base = d.filename.lower().replace("_", " ")
        if document_terms_of:
            base = f"{base} {(document_terms_of(d) or '').lower()}"
        return base

    for ref in references:
        cite_doc = citing_document_of(ref) if citing_document_of else None
        # Same citation from two different documents is two citations; the same
        # citation restated within one document is one.
        if (ref.label, cite_doc) in seen:
            continue
        seen.add((ref.label, cite_doc))
        cite_date = citing_date_of(ref) if citing_date_of else None
        terms = _label_terms(ref.label)

        candidates = [d for d in documents
                      if ref.doc_type_hint and d.doc_type == ref.doc_type_hint
                      and d.id != cite_doc]
        if not candidates:
            token = terms[0] if terms else ref.label.lower()
            if _mentions(uploaded_names, token):
                continue        # named in a filename; treat as present
        else:
            in_window = []
            for d in candidates:
                if terms and not any(_mentions(_terms(d), t) for t in terms):
                    continue    # right kind of document, wrong study
                gap_days = _days_between(cite_date, d.doc_date)
                if gap_days is None:
                    in_window.append(d)     # undated: cannot rule it out
                elif -REFERENCE_LOOKBACK_DAYS <= gap_days <= REFERENCE_LOOKBACK_DAYS:
                    in_window.append(d)
            if in_window:
                best = min(in_window, key=lambda d: abs(
                    _days_between(cite_date, d.doc_date) or 0))
                resolved.append((ref.id, best.id))
                continue

        out.append(EvidenceGap(
            case_id=ref.case_id,
            display_id="",
            gap_type=GapType.MISSING_SOURCE,
            subject_type="document_reference",
            title=ref.label,
            basis=("An uploaded record refers to this document. No other "
                   "uploaded document matches it within "
                   f"{REFERENCE_LOOKBACK_DAYS} days of the citing record, so "
                   "the statements that depend on it cannot be traced to a "
                   "source."),
            status=Status.MISSING,
            subject_id=ref.id,
            evidence_located=[],
            evidence_not_located=[ref.label],
        ))
    return out, resolved


def gaps_from_medications(implicated: list[Medication]) -> list[EvidenceGap]:
    """A medication whose documentation cannot be reconciled across records."""
    out: list[EvidenceGap] = []
    for m in implicated:
        out.append(EvidenceGap(
            case_id=m.case_id,
            display_id="",
            gap_type=GapType.MEDICATION_DOCUMENTATION_GAP,
            subject_type="medication",
            title=m.drug_name,
            basis=("The medication is documented as active in one record and is "
                   "absent from a later medication list, with no stop date "
                   "documented. The records do not state what happened."),
            status=Status.MISSING,
            subject_id=m.id,
            evidence_located=[
                f"Documented active in a record dated {m.record_date}"],
            evidence_not_located=[
                "Entry on the later medication list",
                "A documented stop date or discontinuation note"],
        ))
    return out


def gaps_from_followups(events: list[Event], documents: list[Document],
                        as_of: Optional[str] = None) -> list[EvidenceGap]:
    """A documented expected follow-up with no matching later record.

    Deliberately conservative: it fires only once the pack's expected interval
    has elapsed relative to the latest document in the case, so a follow-up
    that is not yet due is never reported as missing.
    """
    out: list[EvidenceGap] = []
    dated = [(_d(d.doc_date), d) for d in documents if _d(d.doc_date)]
    if not dated:
        return out
    horizon = _d(as_of) or max(dt for dt, _ in dated)

    seen: set[tuple[str, str]] = set()
    for ev in events:
        if ev.event_type != "EXPECTED_FOLLOWUP":
            continue
        ed = _d(ev.event_date)
        if ed is None:
            continue
        label = ev.label or "Expected follow-up"
        interval, wanted = LX.FOLLOWUP_EXPECTATIONS.get(label, (0, None))
        due = ed + timedelta(days=interval)
        if due > horizon:
            continue  # not yet due within the span of the uploaded record
        later = [d for dt, d in dated
                 if dt > ed and (wanted is None or d.doc_type == wanted)]
        if later:
            continue
        key = (label, wanted or "")
        if key in seen:
            continue
        seen.add(key)
        wanted_label = DocType.LABELS.get(wanted, "follow-up") if wanted else "follow-up"
        out.append(EvidenceGap(
            case_id=ev.case_id,
            display_id="",
            gap_type=GapType.MISSING_FOLLOWUP,
            subject_type="event",
            title=label,
            basis=(f"A record dated {ev.event_date} documents this expected "
                   f"follow-up. The expected interval of {interval} days has "
                   f"elapsed within the span of the uploaded records and no "
                   f"matching later document was located."),
            status=Status.MISSING,
            subject_id=ev.id,
            evidence_located=[f"Follow-up instruction documented {ev.event_date}"],
            evidence_not_located=[
                f"A {wanted_label} dated after {due.isoformat()}"],
        ))
    return out
