"""Modality packs and qualitative-finding auditing.

A patient's records are not only laboratory reports. These tests pin the two
properties that make multi-modality support real rather than nominal:

  1. Packs compose without one shadowing another, and an ambiguous term is
     reported as ambiguous instead of being silently assigned to one modality.
  2. A qualitative finding ('no acute infarct') is audited with the same
     machinery as a number -- extracted with provenance, and surfaced as a
     conflict when two documents state mutually exclusive findings.
"""
from __future__ import annotations

import pytest

from caretrace.core.extract import extract_findings
from caretrace.core.engine import conflicts as CE
from caretrace.core.models import Fact
from caretrace.packs import registry as R
from caretrace.packs.medical import lexicon as LX


# --------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------

def test_all_declared_packs_are_active():
    keys = {p["key"] for p in LX.pack_summary()}
    assert keys == {"laboratory", "imaging", "cardiology",
                    "neurophysiology", "molecular"}


def test_every_pack_contributes_vocabulary():
    for p in LX.pack_summary():
        assert p["concepts"] or p["status_concepts"], p


def test_concept_keys_are_globally_unique():
    # _merge_unique raises on collision; reaching the composed dict means the
    # packs did not shadow each other.
    total = sum(len(p.concepts) for p in R.PACKS)
    assert len(LX.CONCEPTS) == total


def test_laboratory_vocabulary_survived_the_split():
    # The original 12 MVP analytes must still be present and unchanged.
    for key in ("hemoglobin", "rbc", "hematocrit", "mcv", "mch", "mchc",
                "rdw", "wbc", "platelets", "ferritin", "creatinine", "glucose"):
        assert key in LX.CONCEPTS
        assert LX.modality_of(key) == "LABORATORY"


def test_new_modalities_are_reachable_by_synonym():
    for surface, expected in [("LVEF", "ejection_fraction"),
                              ("QTc", "qtc_interval"),
                              ("Agatston score", "calcium_score"),
                              ("nerve conduction velocity", "nerve_conduction_velocity"),
                              ("viral load", "viral_load"),
                              ("TMB", "tumor_mutational_burden")]:
        assert LX.SYNONYM_INDEX.get(surface.lower()) == expected, surface


def test_ambiguous_synonyms_are_dropped_not_arbitrated():
    """A term two packs both claim must not resolve to whichever imported first.

    Dropping it makes the label UNRECOGNISED, which is retained as an unmapped
    measurement -- CARETRACE saw a value it cannot confidently name, which is
    the honest outcome and reviewable. Silently picking a modality is not.
    """
    for surface in LX.AMBIGUOUS_SYNONYMS:
        assert surface not in LX.SYNONYM_INDEX
    # The shipped packs are currently collision-free; the guarantee is that if
    # that changes, the term is dropped rather than arbitrated.
    assert LX.AMBIGUOUS_SYNONYMS == {}


def test_a_colliding_pack_raises_rather_than_shadowing():
    from caretrace.packs.base import ConceptDef, Pack
    dup = Pack(key="rogue", label="Rogue", modality="OTHER",
               concepts={"hemoglobin": ConceptDef(
                   "hemoglobin", "Hb", "g/dL", 1.0, 0.1, ("hb",))})
    with pytest.raises(R.PackCollision):
        R._merge_unique((R.PACKS_BY_KEY["laboratory"], dup),
                        "concepts", lambda c: c.key)


def test_conflict_windows_are_modality_appropriate():
    """A repeat CBC and a repeat MRI are not the same episode length."""
    assert LX.conflict_window_days("hemoglobin") <= 7
    assert LX.conflict_window_days("lesion_size") >= 14
    assert LX.conflict_window_days("her2_ratio") >= 180


# --------------------------------------------------------------------------
# Qualitative findings
# --------------------------------------------------------------------------

def test_finding_extracted_with_value_class_and_provenance():
    text = "MRI BRAIN\nFindings: No acute infarct identified."
    items = extract_findings(text, "2026-06-01")
    assert len(items) == 1
    it = items[0]
    assert it.payload["concept"] == "acute_infarct"
    assert it.payload["value_key"] == "ABSENT"
    assert it.payload["modality"] == "IMAGING"
    # Provenance: the span must point back at the sentence as written.
    assert text[it.char_start:it.char_end].strip() == "Findings: No acute infarct identified."


def test_negated_phrase_is_not_recorded_as_positive():
    """'No acute infarct' must never become the finding 'acute infarct'."""
    items = extract_findings("No acute infarct. No intracranial bleed.", "2026-06-01")
    keys = {(i.payload["concept"], i.payload["value_key"]) for i in items}
    assert ("acute_infarct", "ABSENT") in keys
    assert ("acute_infarct", "PRESENT") not in keys
    assert ("hemorrhage", "ABSENT") in keys


def test_positive_finding_is_recorded_when_actually_stated():
    items = extract_findings("Impression: Acute infarct in the left MCA territory.",
                             "2026-06-01")
    assert [(i.payload["concept"], i.payload["value_key"]) for i in items] \
        == [("acute_infarct", "PRESENT")]


def test_hypothetical_frame_yields_no_documented_finding():
    """'Repeat CT if consolidation develops' documents no consolidation."""
    assert extract_findings("Advise repeat CT if consolidation develops.",
                            "2026-06-01") == []
    assert extract_findings("CT ordered to exclude metastases.", "2026-06-01") == []


def test_generic_result_word_requires_a_label_anchor():
    """'Detected' alone is meaningless; next to a label it is the result."""
    assert extract_findings("HBV DNA: Detected", "2026-06-01")[0] \
        .payload["value_key"] == "POSITIVE"
    # The same word inside prose about something else must not be harvested.
    assert extract_findings(
        "No abnormality was detected on clinical examination.", "2026-06-01") == []


def test_multiple_modalities_in_one_report():
    items = extract_findings(
        "ECG: Sinus rhythm. No acute ST-T changes.\n"
        "MRI: No acute infarct.\nEGFR: wild type.", "2026-06-01")
    mods = {i.payload["modality"] for i in items}
    assert mods == {"CARDIOLOGY", "IMAGING", "MOLECULAR"}


def _fact(concept, value_key, date, fid):
    return Fact(case_id="c", display_id=fid, concept=concept,
                surface_form=value_key, source_id=f"s-{fid}",
                value_key=value_key, value_text=value_key,
                obs_date=date, id=fid)


def test_mutually_exclusive_findings_conflict():
    facts = [_fact("acute_infarct", "ABSENT", "2026-06-14", "F1"),
             _fact("acute_infarct", "PRESENT", "2026-06-15", "F2")]
    docs = {"F1": "docA", "F2": "docB"}
    conflicts, rels = CE.detect_status_conflicts(facts, lambda f: docs[f.id])
    assert len(conflicts) == 1
    cf = conflicts[0]
    assert cf.conflict_type == "STATUS_STATEMENT"
    assert cf.status == "UNRESOLVED"
    # Neither side is selected: both summaries are present, no verdict.
    assert {cf.left_summary, cf.right_summary} == {"No acute infarct",
                                                  "Acute infarct present"}
    assert len(rels) == 1


def test_same_finding_worded_differently_does_not_conflict():
    """'No acute infarct' and 'no infarct' are one finding, not a disagreement."""
    a = extract_findings("No acute infarct.", "2026-06-14")[0]
    b = extract_findings("No infarct.", "2026-06-15")[0]
    assert a.payload["value_key"] == b.payload["value_key"]
    facts = [_fact("acute_infarct", a.payload["value_key"], "2026-06-14", "F1"),
             _fact("acute_infarct", b.payload["value_key"], "2026-06-15", "F2")]
    docs = {"F1": "docA", "F2": "docB"}
    conflicts, _ = CE.detect_status_conflicts(facts, lambda f: docs[f.id])
    assert conflicts == []


def test_findings_far_apart_are_not_a_conflict():
    """Findings outside the episode window are change over time, not conflict."""
    facts = [_fact("acute_infarct", "ABSENT", "2026-01-01", "F1"),
             _fact("acute_infarct", "PRESENT", "2026-11-01", "F2")]
    docs = {"F1": "docA", "F2": "docB"}
    conflicts, _ = CE.detect_status_conflicts(facts, lambda f: docs[f.id])
    assert conflicts == []


def test_restatement_within_one_document_is_not_a_conflict():
    facts = [_fact("rhythm", "SINUS", "2026-06-14", "F1"),
             _fact("rhythm", "AF", "2026-06-14", "F2")]
    conflicts, _ = CE.detect_status_conflicts(facts, lambda f: "docA")
    assert conflicts == []


# ---------------------------------------------------------------------------
# Classification and citation resolution.
#
# Both properties below were real defects. A modality whose reports classify as
# OTHER cannot answer a citation of its kind, and a citation pattern that is not
# anchored on a citing verb matches a report's own title -- which makes a
# document appear to cite itself and silently resolves a genuine gap.
# ---------------------------------------------------------------------------

def test_every_pack_declares_the_document_kinds_it_issues():
    """A modality owns its report headings, so core never enumerates them."""
    from caretrace.core.models import DocType
    for pack in LX.PACKS:
        for doc_type, phrases in pack.document_cues:
            assert doc_type in DocType.ALL, f"{pack.key}: unknown {doc_type}"
            assert phrases, f"{pack.key}: {doc_type} declared with no cues"


def test_modality_reports_do_not_classify_as_other():
    from caretrace.core.extract import classify_text
    cases = [
        ("ELECTROCARDIOGRAM REPORT\nRate 78 /min\nPR interval 148 ms",
         "13_ECG_Report_Feb.pdf", "ECG_REPORT"),
        ("MRI BRAIN REPORT\nAccession: X\nNo acute infarct.",
         "16_MRI_Brain_Jun.pdf", "IMAGING_REPORT"),
        ("ELECTROENCEPHALOGRAM REPORT\nPosterior dominant rhythm 9 Hz",
         "18_EEG_Report_Jun.pdf", "EEG_REPORT"),
        ("MOLECULAR DIAGNOSTICS REPORT\nAssay: real-time PCR\nCycle threshold 32",
         "19_Molecular_Report_Jul.pdf", "MOLECULAR_REPORT"),
    ]
    for text, filename, expected in cases:
        assert classify_text(text, filename) == expected, filename


def test_a_report_does_not_cite_itself():
    """A title is not a citation.

    'CT ABDOMEN REPORT' as a heading must not register as a reference to a CT
    report, or the document resolves its own citation and the gap disappears.
    """
    from caretrace.core.extract import extract_references
    title_page = ("CT ABDOMEN REPORT\nNORTHFIELD IMAGING CENTRE (SYNTHETIC)\n"
                  "Findings: Spleen 12.4 cm. No focal lesion.\n")
    assert extract_references(title_page) == []


def test_a_citation_is_detected_across_a_line_break():
    """Layout must not hide a citation.

    Reports wrap mid-sentence, so matching happens on a whitespace-flattened
    view while provenance still points at the original characters.
    """
    from caretrace.core.extract import extract_references
    page = ("Imaging was performed; CT findings as\n"
            "described in the CT report.\n")
    refs = extract_references(page)
    assert [r.payload["label"] for r in refs] == ["CT report"]
    assert page[refs[0].char_start:refs[0].char_end] in page


def test_a_claim_of_normality_is_supported_by_documented_absences():
    """Qualitative evidence counts.

    An impression of 'Study is unremarkable' is supported by the report's own
    negative findings. Reading only numbers reports it as unsupported.
    """
    from caretrace.core.engine.claims_engine import resolve_claims
    from caretrace.core.models import (Claim, ClaimEvidenceStatus, Fact,
                                       EvidenceType)
    claim = Claim(case_id="c", display_id="C-001",
                  claim_text="Study is unremarkable", source_id="s",
                  claim_type="IMAGING_NORMAL", claim_date="2026-06-16")
    facts = [Fact(case_id="c", display_id="F-001", concept="acute_infarct",
                  surface_form="No acute infarct", source_id="s",
                  evidence_type=EvidenceType.OBSERVATION,
                  value_key="ABSENT", value_text="Absent",
                  obs_date="2026-06-15")]
    results, rels = resolve_claims([claim], facts)
    assert results[0]["status"] == ClaimEvidenceStatus.SUPPORTING_EVIDENCE
    assert len(results[0]["supporting"]) == 1
    assert any(r.rel_type == "SUPPORTS" for r in rels)


def test_a_positive_finding_contradicts_a_claim_of_normality():
    """The same machinery, the other direction -- and no adjudication."""
    from caretrace.core.engine.claims_engine import resolve_claims
    from caretrace.core.models import (Claim, ClaimEvidenceStatus, Fact,
                                       EvidenceType)
    claim = Claim(case_id="c", display_id="C-001",
                  claim_text="Study is unremarkable", source_id="s",
                  claim_type="IMAGING_NORMAL", claim_date="2026-06-16")
    facts = [Fact(case_id="c", display_id="F-001", concept="acute_infarct",
                  surface_form="Acute infarct noted", source_id="s",
                  evidence_type=EvidenceType.OBSERVATION,
                  value_key="PRESENT", value_text="Present",
                  obs_date="2026-06-15")]
    results, _ = resolve_claims([claim], facts)
    assert results[0]["status"] == ClaimEvidenceStatus.CONTRADICTING_EVIDENCE


def test_status_evidence_requires_a_declared_polarity():
    """Silence in the pack is not an assumption.

    A claim type that declares no status polarity takes no qualitative
    evidence, rather than the engine guessing what the claim meant.
    """
    for ct in LX.CLAIM_TYPES:
        stat = [c for c in ct.requires_any if c in LX.STATUS_CONCEPTS]
        if stat:
            assert ct.supportive_status_polarity is not None, (
                f"{ct.key} requires qualitative findings but declares no "
                "polarity, so the engine cannot use them")
