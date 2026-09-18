"""Unit tests for the deterministic audit engine.

These tests construct facts directly, so they test the engine's rules rather
than the demo corpus. The most important tests here are the negative ones: that
the engine does NOT pick a winner, does NOT call a gap a falsehood, and does
NOT report a single disagreement twice.
"""
from __future__ import annotations

import pytest

from caretrace.core import models as M
from caretrace.core.engine import changes as CH
from caretrace.core.engine import claims_engine as CL
from caretrace.core.engine import conflicts as CF
from caretrace.core.engine import gaps as GP

CASE = "case-1"


def fact(concept, value, date, unit="g/dL", doc="doc-a", conf=0.98, fid=None):
    f = M.Fact(case_id=CASE, display_id=fid or f"F-{concept}-{date}-{value}",
               concept=concept, surface_form=concept, source_id=f"src-{doc}-{date}-{value}",
               evidence_type=M.EvidenceType.OBSERVATION, value_num=value,
               value_text=None, unit=unit, obs_date=date, date_precision="day",
               confidence=conf)
    f._doc = doc  # test-only tag read by the doc_of callable below
    return f


def doc_of(f):
    return getattr(f, "_doc", None)


# --------------------------------------------------------------------------
# Changes
# --------------------------------------------------------------------------

def test_longitudinal_change_is_detected():
    facts = [fact("hemoglobin", 9.2, "2026-01-18"),
             fact("hemoglobin", 10.4, "2026-03-15"),
             fact("hemoglobin", 8.7, "2026-06-14")]
    rows, rels = CH.detect_changes(facts)
    assert [(r.from_value, r.to_value) for r in rows] == [(9.2, 10.4), (10.4, 8.7)]
    assert {r.rel_type for r in rels} == {M.RelType.CHANGED_TO, M.RelType.CHANGED_FROM}


def test_change_language_is_neutral():
    """The engine must not editorialise about the patient."""
    rows, _ = CH.detect_changes([fact("hemoglobin", 12.0, "2026-01-01"),
                                 fact("hemoglobin", 7.0, "2026-06-01")])
    text = " ".join(r.basis.lower() for r in rows)
    for banned in ("deteriorat", "worsen", "improv", "should", "diagnos",
                   "patient is", "abnormal"):
        assert banned not in text, f"engine editorialised: {banned!r} in {text!r}"
    assert "documented" in text


def test_same_episode_pair_is_not_a_change():
    """Two values one day apart are a conflict, not a change over time."""
    rows, _ = CH.detect_changes([fact("hemoglobin", 8.7, "2026-06-14", doc="a"),
                                 fact("hemoglobin", 12.1, "2026-06-15", doc="b")])
    assert rows == []


def test_identical_repeat_is_not_a_change():
    rows, _ = CH.detect_changes([fact("hemoglobin", 9.2, "2026-01-18", doc="a"),
                                 fact("hemoglobin", 9.2, "2026-03-18", doc="b")])
    assert rows == []


def test_duplicate_relationship_is_recorded():
    rels = CH.detect_duplicates([fact("hemoglobin", 9.2, "2026-01-18", doc="a"),
                                 fact("hemoglobin", 9.2, "2026-01-18", doc="b")])
    assert len(rels) == 1 and rels[0].rel_type == M.RelType.DUPLICATES


# --------------------------------------------------------------------------
# Conflicts
# --------------------------------------------------------------------------

def test_numeric_conflict_detected_and_left_unresolved():
    conflicts, rels = CF.detect_numeric_conflicts(
        [fact("hemoglobin", 8.7, "2026-06-14", doc="cbc"),
         fact("hemoglobin", 12.1, "2026-06-15", doc="discharge")], doc_of)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.status == M.Status.UNRESOLVED
    assert {c.left_summary, c.right_summary} == {"8.7 g/dL", "12.1 g/dL"}
    assert any(r.rel_type == M.RelType.CONTRADICTS for r in rels)


def test_conflict_never_declares_a_winner():
    conflicts, _ = CF.detect_numeric_conflicts(
        [fact("hemoglobin", 8.7, "2026-06-14", doc="cbc"),
         fact("hemoglobin", 12.1, "2026-06-15", doc="discharge")], doc_of)
    text = conflicts[0].basis.lower()
    for banned in ("correct value", "is correct", "true value", "actual value",
                   "should be", "resolved to", "more reliable", "incorrect"):
        assert banned not in text
    assert "does not select" in text


def test_immaterial_difference_is_not_a_conflict():
    """Within the pack's materiality threshold, two readings agree."""
    conflicts, _ = CF.detect_numeric_conflicts(
        [fact("hemoglobin", 9.2, "2026-06-14", doc="a"),
         fact("hemoglobin", 9.4, "2026-06-15", doc="b")], doc_of)
    assert conflicts == []


def test_values_far_apart_in_time_are_a_change_not_a_conflict():
    conflicts, _ = CF.detect_numeric_conflicts(
        [fact("hemoglobin", 9.2, "2026-01-18", doc="a"),
         fact("hemoglobin", 12.1, "2026-06-15", doc="b")], doc_of)
    assert conflicts == []


def test_same_document_restatement_is_not_a_conflict():
    conflicts, _ = CF.detect_numeric_conflicts(
        [fact("hemoglobin", 8.7, "2026-06-14", doc="same"),
         fact("hemoglobin", 12.1, "2026-06-15", doc="same")], doc_of)
    assert conflicts == []


def test_restated_value_is_one_conflict_with_all_sources():
    """A value repeated across documents must not multiply the finding."""
    facts = [fact("hemoglobin", 8.7, "2026-06-14", doc="cbc"),
             fact("hemoglobin", 8.7, "2026-06-14", doc="summary"),
             fact("hemoglobin", 8.7, "2026-06-14", doc="followup"),
             fact("hemoglobin", 12.1, "2026-06-15", doc="discharge"),
             fact("hemoglobin", 12.1, "2026-06-15", doc="followup")]
    conflicts, _ = CF.detect_numeric_conflicts(facts, doc_of)
    assert len(conflicts) == 1, "one disagreement should be one finding"
    c = conflicts[0]
    assert len(c.left_member_ids) == 3 and len(c.right_member_ids) == 2
    # every contributing record keeps its provenance
    assert set(c.left_member_ids) | set(c.right_member_ids) == {f.id for f in facts}


def test_medication_absent_from_later_list_is_a_documentation_conflict():
    rx = M.Medication(case_id=CASE, display_id="M-1", drug_name="Ferrous sulfate",
                      drug_norm="ferrous sulfate", source_id="s1", dose=100.0,
                      unit="mg", frequency="once daily", route="oral",
                      status="ACTIVE", start_date="2026-01-20", stop_date=None,
                      record_date="2026-01-20", confidence=0.95)
    other = M.Medication(case_id=CASE, display_id="M-2", drug_name="Paracetamol",
                         drug_norm="paracetamol", source_id="s2", dose=500.0,
                         unit="mg", frequency="as needed", route="oral",
                         status="ACTIVE", start_date=None, stop_date=None,
                         record_date="2026-06-15", confidence=0.95)
    docs = {rx.id: "rx-doc", other.id: "list-doc"}
    types = {rx.id: "PRESCRIPTION", other.id: "MEDICATION_LIST"}
    conflicts, rels, implicated = CF.detect_medication_conflicts(
        [rx, other], lambda m: docs[m.id], lambda m: types[m.id],
        lambda d: "09_Medication_List.pdf")
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == M.ConflictType.MEDICATION_DOCUMENTATION
    assert conflicts[0].status == M.Status.UNRESOLVED
    assert implicated == [rx]
    # must not infer discontinuation
    assert "does not infer" in conflicts[0].basis.lower()
    assert "stopped taking" not in conflicts[0].basis.lower()


def test_documented_stop_date_is_not_a_conflict():
    rx = M.Medication(case_id=CASE, display_id="M-1", drug_name="Ferrous sulfate",
                      drug_norm="ferrous sulfate", source_id="s1", dose=100.0,
                      unit="mg", frequency="once daily", route="oral",
                      status="ACTIVE", start_date="2026-01-20",
                      stop_date="2026-05-01", record_date="2026-01-20",
                      confidence=0.95)
    other = M.Medication(case_id=CASE, display_id="M-2", drug_name="Paracetamol",
                         drug_norm="paracetamol", source_id="s2", dose=500.0,
                         unit="mg", frequency="prn", route="oral", status="ACTIVE",
                         start_date=None, stop_date=None, record_date="2026-06-15",
                         confidence=0.95)
    docs = {rx.id: "rx-doc", other.id: "list-doc"}
    types = {rx.id: "PRESCRIPTION", other.id: "MEDICATION_LIST"}
    conflicts, _, _ = CF.detect_medication_conflicts(
        [rx, other], lambda m: docs[m.id], lambda m: types[m.id], lambda d: "list")
    assert conflicts == []


# --------------------------------------------------------------------------
# Claims and gaps
# --------------------------------------------------------------------------

def claim(text, ctype, date):
    return M.Claim(case_id=CASE, display_id="C-1", claim_text=text,
                   source_id="src-c", claim_type=ctype, claim_date=date,
                   date_precision="day", confidence=0.85,
                   evidence_status=M.ClaimEvidenceStatus.NOT_ASSESSED)


def test_claim_without_evidence_is_not_located_not_false():
    c = claim("Iron deficiency confirmed", "IRON_DEFICIENCY", "2026-02-09")
    results, rels = CL.resolve_claims([c], [fact("hemoglobin", 9.2, "2026-01-18")])
    assert results[0]["status"] == M.ClaimEvidenceStatus.NO_LOCATED_EVIDENCE
    gaps = GP.gaps_from_claims(results)
    assert len(gaps) == 1
    text = (gaps[0].basis + " " + gaps[0].status).lower()
    for banned in ("false", "incorrect", "wrong", "unfounded", "disproven"):
        assert banned not in text
    assert "not located" in text or gaps[0].status == M.Status.MISSING
    assert any(r.rel_type == M.RelType.MISSING_SUPPORT for r in rels)


def test_evidence_after_the_claim_does_not_support_it():
    """Ferritin drawn two months AFTER the claim cannot retroactively support it."""
    c = claim("Iron deficiency confirmed", "IRON_DEFICIENCY", "2026-02-09")
    later = fact("ferritin", 18.0, "2026-04-12", unit="ng/mL")
    results, _ = CL.resolve_claims([c], [later])
    assert results[0]["status"] == M.ClaimEvidenceStatus.NO_LOCATED_EVIDENCE


def test_gap_discloses_evidence_that_exists_but_is_out_of_window():
    """A reviewer who has seen the ferritin result elsewhere in the records must
    be told WHY it does not count here, or "not located" reads as a miss."""
    c = claim("Iron deficiency confirmed", "IRON_DEFICIENCY", "2026-02-09")
    later = fact("ferritin", 18.0, "2026-04-12", unit="ng/mL")
    results, _ = CL.resolve_claims([c], [later])
    oow = results[0]["out_of_window"]
    assert [o["reason"] for o in oow] == ["after_claim"]
    basis = GP.gaps_from_claims(results)[0].basis
    assert "2026-04-12" in basis and "dated after this claim" in basis
    # Still a statement about the records, never about the claim's truth.
    for banned in ("false", "incorrect", "unfounded"):
        assert banned not in basis.lower()


def test_out_of_window_note_is_not_repeated_per_restatement():
    """One ferritin value restated in three documents is one dating problem."""
    c = claim("Iron deficiency confirmed", "IRON_DEFICIENCY", "2026-02-09")
    restated = [fact("ferritin", 18.0, "2026-04-12", unit="ng/mL") for _ in range(3)]
    results, _ = CL.resolve_claims([c], restated)
    assert len(results[0]["out_of_window"]) == 3
    assert GP.gaps_from_claims(results)[0].basis.count("dated after this claim") == 1


def test_claim_with_evidence_is_supported():
    c = claim("Iron deficiency confirmed", "IRON_DEFICIENCY", "2026-06-15")
    earlier = fact("ferritin", 18.0, "2026-04-12", unit="ng/mL")
    results, rels = CL.resolve_claims([c], [earlier])
    assert results[0]["status"] == M.ClaimEvidenceStatus.SUPPORTING_EVIDENCE
    assert any(r.rel_type == M.RelType.SUPPORTS for r in rels)
    assert GP.gaps_from_claims(results) == []


def test_claim_contradicted_by_the_record():
    c = claim("Haemoglobin normalised", "HB_NORMALIZED", "2026-06-15")
    results, rels = CL.resolve_claims([c], [fact("hemoglobin", 8.7, "2026-06-14")])
    assert results[0]["status"] == M.ClaimEvidenceStatus.CONTRADICTING_EVIDENCE
    assert any(r.rel_type == M.RelType.CONTRADICTS for r in rels)


def test_missing_referenced_document_is_a_gap():
    ref = M.DocumentReference(case_id=CASE, display_id="R-1", label="CT report",
                              source_id="src-r", doc_type_hint="IMAGING_REPORT",
                              resolved_document_id=None, status=M.Status.MISSING)
    doc = M.Document(case_id=CASE, filename="08_Discharge.pdf",
                     doc_type="DISCHARGE_SUMMARY", doc_date="2026-06-15",
                     page_count=3, byte_size=1, sha256="x", stored_path="p",
                     upload_status="UPLOADED", processing_status="PROCESSED",
                     processing_note=None, ordinal=1)
    gaps, resolved = GP.gaps_from_references([ref], [doc])
    assert len(gaps) == 1 and gaps[0].gap_type == M.GapType.MISSING_SOURCE
    assert resolved == []


def test_reference_to_an_uploaded_document_is_not_a_gap():
    ref = M.DocumentReference(case_id=CASE, display_id="R-1", label="CT report",
                              source_id="src-r", doc_type_hint="IMAGING_REPORT",
                              resolved_document_id=None, status=M.Status.MISSING)
    ct = M.Document(case_id=CASE, filename="99_CT_Abdomen.pdf",
                    doc_type="IMAGING_REPORT", doc_date="2026-06-10", page_count=1,
                    byte_size=1, sha256="x", stored_path="p",
                    upload_status="UPLOADED", processing_status="PROCESSED",
                    processing_note=None, ordinal=1)
    gaps, resolved = GP.gaps_from_references([ref], [ct],
                                             lambda r: "2026-06-15")
    assert gaps == []
    # The satisfied citation names the document that answered it.
    assert resolved == [(ref.id, ct.id)]


def test_reference_is_not_satisfied_by_a_distant_study():
    """A June discharge citing 'the CT report' does not mean January's CT.

    Matching on modality alone would let any same-kind document ever uploaded
    answer the citation, silently erasing a real documentation gap.
    """
    ref = M.DocumentReference(case_id=CASE, display_id="R-1", label="CT report",
                              source_id="src-r", doc_type_hint="IMAGING_REPORT",
                              resolved_document_id=None, status=M.Status.MISSING)
    old_ct = M.Document(case_id=CASE, filename="02_CT_Jan.pdf",
                        doc_type="IMAGING_REPORT", doc_date="2026-01-05",
                        page_count=1, byte_size=1, sha256="x", stored_path="p",
                        upload_status="UPLOADED", processing_status="PROCESSED",
                        processing_note=None, ordinal=1)
    gaps, resolved = GP.gaps_from_references([ref], [old_ct],
                                             lambda r: "2026-06-15")
    assert len(gaps) == 1
    assert resolved == []


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def test_engine_is_deterministic_under_input_order():
    import random
    facts = [fact("hemoglobin", 9.2, "2026-01-18", doc="a"),
             fact("hemoglobin", 10.4, "2026-03-15", doc="b"),
             fact("hemoglobin", 8.7, "2026-06-14", doc="c"),
             fact("hemoglobin", 12.1, "2026-06-15", doc="d")]
    baseline_changes = [(c.from_value, c.to_value) for c in CH.detect_changes(facts)[0]]
    baseline_conflicts = [(c.left_summary, c.right_summary)
                          for c in CF.detect_numeric_conflicts(facts, doc_of)[0]]
    rng = random.Random(0)
    for _ in range(12):
        shuffled = facts[:]
        rng.shuffle(shuffled)
        assert [(c.from_value, c.to_value)
                for c in CH.detect_changes(shuffled)[0]] == baseline_changes
        assert [(c.left_summary, c.right_summary)
                for c in CF.detect_numeric_conflicts(shuffled, doc_of)[0]] == baseline_conflicts
