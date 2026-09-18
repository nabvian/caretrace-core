"""Integration test: the demo corpus through the real ingestion path.

Asserts that each finding the corpus was designed to contain is actually
DERIVED from the rendered PDFs — not planted. The corpus module states the
intended findings in its docstring; this file is where those intentions are
checked against what the engine independently produces.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from caretrace.core import models as M
from caretrace.core import pipeline as P
from caretrace.core.store import Store
from caretrace.demo.render_pdfs import PDF_DIR, render_all


@pytest.fixture(scope="module")
def audited(tmp_path_factory):
    out = tmp_path_factory.mktemp("pdfs")
    render_all(out)
    store = Store()
    case = store.insert(M.Case(case_ref="CT-DEMO-001",
                               subject_label="Arjun Mehta (synthetic)",
                               is_synthetic=True))
    store.commit()
    for i, p in enumerate(sorted(Path(out).glob("*.pdf")), start=1):
        P.ingest_document(store, case.id, p, i)
    store.commit()
    result = P.process_case(store, case.id)
    return store, case.id, result


def rows(store, table, case_id):
    return store.rows(table, case_id)


def test_all_documents_ingested(audited):
    store, cid, res = audited
    # The corpus spans five modalities; counts are asserted against the
    # generator so a document added without a matching page count fails here.
    from caretrace.demo.case_ct_demo_001 import DOCUMENTS
    assert res.counts["documents"] == len(DOCUMENTS)
    assert res.counts["pages"] >= res.counts["documents"]


def test_every_document_is_classified(audited):
    """No document falls through to OTHER.

    A document typed OTHER cannot answer a citation of its kind, so an
    unclassified report silently turns a resolved reference into a false gap.
    """
    store, cid, _ = audited
    unclassified = [d["filename"] for d in rows(store, "documents", cid)
                    if d["doc_type"] == M.DocType.OTHER]
    assert unclassified == []


def test_all_five_modalities_are_represented(audited):
    """The packs demonstrate rather than merely exist."""
    store, cid, _ = audited
    # Modality is a property of the concept, so it is asked of the pack rather
    # than stored on the row -- one source of truth, no column to drift.
    from caretrace.packs.medical import lexicon as LX
    modalities = {LX.modality_of(f["concept"]) for f in rows(store, "facts", cid)}
    assert {"LABORATORY", "IMAGING", "CARDIOLOGY", "NEUROPHYSIOLOGY",
            "MOLECULAR"} <= modalities


def test_imaging_status_conflict_is_detected(audited):
    """Two reports state opposite findings for the same concept.

    The MRI reports no acute infarct; the neurology note the next day states
    one. Neither side is selected.
    """
    store, cid, _ = audited
    conflicts = [c for c in rows(store, "conflicts", cid)
                 if c["conflict_type"] == M.ConflictType.STATUS_STATEMENT]
    assert conflicts, "expected a qualitative finding conflict"
    c = conflicts[0]
    assert c["status"] == M.Status.UNRESOLVED
    assert c["left_summary"] != c["right_summary"]


def test_qualitative_findings_support_a_normality_claim(audited):
    """A radiology or EEG impression is evidenced by the report's own findings.

    Most of a radiology result is stated as text. If the claim engine reads only
    numbers, every such impression is reported as unsupported -- a false gap
    that would train a reviewer to ignore the gap list.
    """
    store, cid, _ = audited
    claims = rows(store, "claims", cid)
    normality = [c for c in claims
                 if c["claim_type"] in ("IMAGING_NORMAL", "EEG_NORMAL")]
    assert normality, "expected a normality impression in the corpus"
    assert all(c["evidence_status"] != M.ClaimEvidenceStatus.NO_LOCATED_EVIDENCE
               for c in normality)


def test_every_fact_is_source_traceable(audited):
    """The product promise: no finding without provenance."""
    store, cid, res = audited
    assert res.counts["source_traceability"] == 1.0
    for f in rows(store, "facts", cid):
        src = store.source(f["source_id"])
        assert src and src["filename"] and src["page_number"] >= 1
        assert src["source_text"].strip(), f"{f['display_id']} has empty source text"


def test_hemoglobin_longitudinal_change(audited):
    store, cid, _ = audited
    hb = [(c["from_value"], c["to_value"]) for c in rows(store, "changes", cid)
          if c["concept"] == "hemoglobin"]
    assert (9.2, 10.4) in hb and (10.4, 8.7) in hb


def test_hemoglobin_conflict_is_unresolved_with_both_sources(audited):
    store, cid, _ = audited
    hb = [c for c in rows(store, "conflicts", cid) if c["concept"] == "hemoglobin"]
    assert len(hb) == 1, "the restated Hb disagreement must be one finding"
    c = hb[0]
    assert c["status"] == M.Status.UNRESOLVED
    assert {c["left_summary"], c["right_summary"]} == {"8.7 g/dL", "12.1 g/dL"}
    docs = set()
    for mid in c["left_member_ids"] + c["right_member_ids"]:
        f = store.q1("SELECT source_id FROM facts WHERE id = ?", (mid,))
        docs.add(store.source(f["source_id"])["filename"])
    assert "07_CBC_Jun.pdf" in docs and "08_Discharge_Summary_Jun.pdf" in docs


def test_platelet_conflict_detected(audited):
    store, cid, _ = audited
    plt = [c for c in rows(store, "conflicts", cid) if c["concept"] == "platelets"]
    assert len(plt) == 1
    assert {plt[0]["left_summary"], plt[0]["right_summary"]} == \
           {"186 x10^9/L", "402 x10^9/L"}


def test_medication_documentation_conflict(audited):
    store, cid, _ = audited
    med = [c for c in rows(store, "conflicts", cid)
           if c["conflict_type"] == M.ConflictType.MEDICATION_DOCUMENTATION
           and c["concept"] == "ferrous sulfate"]
    assert len(med) == 1 and med[0]["status"] == M.Status.UNRESOLVED


def test_unsupported_iron_deficiency_claim(audited):
    store, cid, _ = audited
    gaps = [g for g in rows(store, "evidence_gaps", cid)
            if g["gap_type"] == M.GapType.MISSING_SUPPORTING_TEST
            and "iron deficiency" in g["title"].lower()]
    assert len(gaps) == 1
    assert "ferritin" in " ".join(gaps[0]["evidence_not_located"]).lower()


def test_missing_referenced_ct_report(audited):
    store, cid, _ = audited
    gaps = [g for g in rows(store, "evidence_gaps", cid)
            if g["gap_type"] == M.GapType.MISSING_SOURCE]
    assert any("ct" in g["title"].lower() for g in gaps), (
        "the June discharge cites a CT from that admission; the April CT is "
        "outside the citation window and must not satisfy it")


def test_scanned_referral_is_extraction_incomplete(audited):
    """A page with no text layer must be reported, not silently skipped."""
    store, cid, _ = audited
    doc = next(d for d in rows(store, "documents", cid)
               if d["filename"] == "10_Referral_Letter.pdf")
    assert doc["processing_status"] == "EXTRACTION_INCOMPLETE"
    assert doc["processing_note"]
    facts = [f for f in rows(store, "facts", cid)
             if store.source(f["source_id"])["document_id"] == doc["id"]]
    assert facts == [], "no values may be invented for an unreadable page"


def test_duplicate_values_are_marked_not_conflicting(audited):
    store, cid, _ = audited
    dupes = store.q(
        "SELECT * FROM relationships WHERE case_id = ? AND rel_type = ?",
        (cid, M.RelType.DUPLICATES))
    assert len(dupes) >= 1


def test_dashboard_counts_match_stored_rows(audited):
    """Metrics must be computed from the data, never hardcoded."""
    store, cid, res = audited
    for table, key in (("facts", "facts"), ("claims", "claims"),
                       ("conflicts", "conflicts"), ("changes", "changes"),
                       ("evidence_gaps", "evidence_gaps"),
                       ("medications", "medications")):
        assert res.counts[key] == store.count(table, cid), key


def test_no_clinical_advice_language_anywhere(audited):
    """Scan every generated string the UI can display."""
    store, cid, _ = audited
    banned = ("you should", "we recommend", "diagnosis is", "treatment should",
              "prescribe", "patient is deteriorating", "correct value is",
              "the true value")
    texts = []
    for t, cols in (("conflicts", ("basis", "left_summary", "right_summary")),
                    ("changes", ("basis",)),
                    ("evidence_gaps", ("title", "basis", "recommended_source")),
                    ("relationships", ("detail",))):
        for r in rows(store, t, cid):
            texts += [str(r[c]) for c in cols if r.get(c)]
    blob = " ".join(texts).lower()
    for phrase in banned:
        assert phrase not in blob, f"clinical-advice language found: {phrase!r}"


def test_rerunning_the_audit_is_stable(audited):
    """A second run must reproduce the same counts — derived data is rebuilt."""
    store, cid, res = audited
    again = P.process_case(store, cid)
    for k in ("facts", "claims", "changes", "conflicts", "evidence_gaps",
              "medications", "relationships"):
        assert again.counts[k] == res.counts[k], k
