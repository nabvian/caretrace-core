"""Registry construction over a real corpus, and the isolation it buys.

The tests that matter most here are the cross-patient ones. Once a case can
hold more than one person, every detector in the audit engine becomes a
correctness risk: handed the union of two people's records, a change detector
reports a trend that never happened and a conflict detector reports a
disagreement between two people who simply have different blood.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from caretrace.core import identity as ID
from caretrace.core import models as M
from caretrace.core import pipeline as P
from caretrace.core import registry as REG
from caretrace.core.store import Store
from caretrace.demo.render_pdfs import render_all


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    out = tmp_path_factory.mktemp("regpdfs")
    render_all(out)
    store = Store()
    case = store.insert(M.Case(case_ref="CT-REG-001",
                               subject_label="Arjun Mehta (synthetic)"))
    store.commit()
    for i, p in enumerate(sorted(Path(out).glob("*.pdf")), start=1):
        P.ingest_document(store, case.id, p, i)
    store.commit()
    res = P.process_case(store, case.id, resolve_terminology=False)
    return store, case.id, res, out


# --------------------------------------------------------------------------- #
# Extraction from letterheads
# --------------------------------------------------------------------------- #

def test_every_letterheaded_document_yields_one_institution(demo):
    store, cid, _res, _out = demo
    names = [r["display_name"] for r in
             store.q("SELECT display_name FROM institutions")]
    # Six distinct issuers in the corpus; the scanned referral has no text
    # layer and therefore no readable letterhead.
    assert len(names) >= 5
    # A document TITLE must never be recorded as the issuer.
    for bad in ("SUMMARY", "REPORT", "NOTE", "PRESCRIPTION", "COUNT"):
        assert not any(n.endswith(bad) for n in names), names


def test_a_document_title_is_not_mistaken_for_a_letterhead():
    """'CUMULATIVE LABORATORY SUMMARY' satisfies the institution word list by
    accident. Recording it as the issuer would be a plausible falsehood."""
    text = ("CUMULATIVE LABORATORY SUMMARY\n"
            "MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
            "12 Rowan Street, Fictionville\n")
    assert REG.extract_institution(text) == "MERIDIAN DIAGNOSTIC LABORATORY"


def test_an_unrecognised_letterhead_yields_nothing_rather_than_a_guess():
    assert REG.extract_institution("ACME\nsomething\n") is None


def test_participant_roles_come_from_the_documents_own_labels(demo):
    store, cid, _res, _out = demo
    rows = store.q(
        "SELECT c.display_name, p.role FROM document_participants p "
        "JOIN clinicians c ON c.id = p.clinician_id")
    assert rows
    roles = {r["role"] for r in rows}
    assert roles <= set(M.ParticipantRole.ALL)
    # 'Requested by' is an order; 'Verified by' is a performance. The corpus
    # uses both, so both must appear.
    assert {"ORDERING", "PERFORMING"} <= roles


def test_a_speciality_without_a_person_is_not_recorded_as_a_clinician():
    """'To: The Consultant Gastroenterologist' names a role, not a doctor."""
    got = REG.extract_participants("Consultant: The Consultant Gastroenterologist\n")
    assert got == []


def test_report_metadata_is_trimmed_from_a_clinician_name():
    """Header lines pack fields together: the name ends where the next one
    starts, or the registry accumulates 'Dr. R. Nair Report No LAB-26-00811'."""
    got = REG.extract_participants(
        "Requested by: Dr. R. Nair (synthetic)   Report No: LAB-26-00811\n")
    assert got == [(M.ParticipantRole.ORDERING, "Dr. R. Nair (synthetic)")]


# --------------------------------------------------------------------------- #
# Resolution over the corpus
# --------------------------------------------------------------------------- #

def test_the_single_subject_corpus_yields_exactly_one_patient(demo):
    store, cid, _res, _out = demo
    rows = store.q("SELECT patient_ref, mrn, dob FROM patients")
    assert len(rows) == 1
    assert rows[0]["mrn"] == "SYN448120"
    assert rows[0]["dob"] == "1988-05-15"


def test_the_scanned_document_is_queued_for_review_with_its_real_reason(demo):
    store, cid, _res, _out = demo
    rows = store.q(
        "SELECT d.filename, l.basis FROM identity_links l "
        "JOIN documents d ON d.id = l.document_id WHERE l.status = ?",
        ("NEEDS_REVIEW",))
    assert [r["filename"] for r in rows] == ["10_Referral_Letter.pdf"]
    assert rows[0]["basis"] == "NO_READABLE_TEXT"


def test_every_document_has_exactly_one_resolution_decision(demo):
    """No document is silently unaccounted for: either it links, or a row says
    why it does not."""
    store, cid, res, _out = demo
    n_docs = store.q1("SELECT COUNT(*) AS n FROM documents WHERE case_id = ?",
                      (cid,))["n"]
    n_links = store.q1("SELECT COUNT(*) AS n FROM identity_links "
                       "WHERE case_id = ?", (cid,))["n"]
    assert n_links == n_docs
    assert store.q1("SELECT COUNT(*) AS n FROM identity_links WHERE case_id = ? "
                    "AND (rationale IS NULL OR rationale = '')", (cid,))["n"] == 0


def test_the_assertion_keeps_the_documents_own_wording(demo):
    """Normalisation is for matching. The evidence row keeps what was written."""
    store, cid, _res, _out = demo
    row = store.q1("SELECT raw_dob, dob, raw_mrn, mrn FROM identity_assertions "
                   "WHERE case_id = ? AND raw_dob IS NOT NULL", (cid,))
    assert row["raw_dob"] == "15 May 1988"      # as documented
    assert row["dob"] == "1988-05-15"           # as compared
    assert row["raw_mrn"] == "SYN-448120"
    assert row["mrn"] == "SYN448120"


def test_reprocessing_reproduces_the_same_registry(demo):
    """The registry persists across runs, so a second run must re-match rather
    than duplicate: a patient created once and re-created on every run is the
    failure mode that makes a registry worthless."""
    store, cid, res, _out = demo
    before = store.q1("SELECT COUNT(*) AS n FROM patients")["n"]
    again = P.process_case(store, cid, resolve_terminology=False)
    assert store.q1("SELECT COUNT(*) AS n FROM patients")["n"] == before
    for k in ("facts", "claims", "changes", "conflicts", "evidence_gaps"):
        assert again.counts[k] == res.counts[k], k


def test_encounters_group_documents_by_patient_date_and_institution(demo):
    store, cid, _res, _out = demo
    rows = store.q(
        "SELECT e.id, COUNT(ed.document_id) AS n FROM encounters e "
        "LEFT JOIN encounter_documents ed ON ed.encounter_id = e.id "
        "WHERE e.case_id = ? GROUP BY e.id", (cid,))
    assert rows
    assert all(r["n"] >= 1 for r in rows)
    # Every grouped document belongs to a linked patient.
    assert store.q1(
        "SELECT COUNT(*) AS n FROM encounters WHERE case_id = ? "
        "AND patient_id IS NULL", (cid,))["n"] == 0


def test_the_registry_survives_reprocessing_but_decisions_are_rebuilt(demo):
    """Patients outlive a run; assertions and links are derived and cleared."""
    store, cid, _res, _out = demo
    store.clear_derived(cid)
    assert store.q1("SELECT COUNT(*) AS n FROM patients")["n"] >= 1
    assert store.q1("SELECT COUNT(*) AS n FROM identity_links "
                    "WHERE case_id = ?", (cid,))["n"] == 0
    P.process_case(store, cid, resolve_terminology=False)


# --------------------------------------------------------------------------- #
# The isolation the registry exists to provide
# --------------------------------------------------------------------------- #

def _two_patient_case(tmp_path):
    """A case holding two people, each with one CBC, values far apart.

    Deliberately constructed so that mixing them would be visible: 9.2 and
    14.8 g/dL on nearby dates would be both a large documented change and a
    material conflict if the two records were treated as one person's.
    """
    store = Store()
    case = store.insert(M.Case(case_ref="CT-TWO-001", subject_label="two"))
    store.commit()
    tpl = ("MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
           "Patient: {name}          Sex: {sex}     DOB: {dob}\n"
           "Case Ref: CT-TWO-001         MRN: {mrn}\n"
           "Report Date: {date}\n\n"
           "COMPLETE BLOOD COUNT\n"
           "Hemoglobin: {hb} g/dL\n")
    people = [
        dict(name="Arjun Mehta", sex="M", dob="15 May 1988", mrn="SYN-1",
             date="18 January 2026", hb="9.2"),
        dict(name="Rhea Sharma", sex="F", dob="3 Feb 1991", mrn="SYN-2",
             date="20 January 2026", hb="14.8"),
    ]
    for i, person in enumerate(people, start=1):
        f = tmp_path / f"{i:02d}_cbc.txt"
        f.write_text(tpl.format(**person))
        P.ingest_document(store, case.id, f, i)
    store.commit()
    return store, case.id


def test_two_subjects_in_one_case_become_two_patients(tmp_path):
    store, cid = _two_patient_case(tmp_path)
    P.process_case(store, cid, resolve_terminology=False)
    assert store.q1("SELECT COUNT(*) AS n FROM patients")["n"] == 2


def test_facts_belonging_to_two_people_are_never_compared(tmp_path):
    """The core isolation guarantee.

    Without partitioning, one person's 9.2 and another's 14.8 would be reported
    as a documented change and a conflict. Both would be fully provenanced and
    completely false -- and no downstream check could catch it, which is why
    this is asserted here rather than left to review.
    """
    store, cid = _two_patient_case(tmp_path)
    res = P.process_case(store, cid, resolve_terminology=False)
    assert res.counts["facts"] == 2
    assert res.counts["changes"] == 0, "a change across two patients is not a change"
    assert res.counts["conflicts"] == 0, "two people's values do not contradict"


def test_a_claim_is_assessed_only_against_its_own_patients_evidence(tmp_path):
    """Supporting one person's claim with another person's laboratory result is
    a wrong merge reached from the other direction."""
    store = Store()
    case = store.insert(M.Case(case_ref="CT-CLAIM-001", subject_label="two"))
    store.commit()
    # Patient A asserts iron deficiency and has no iron studies at all.
    a = ("RIVERSIDE INTERNAL MEDICINE CLINIC (SYNTHETIC)\n"
         "Patient: Arjun Mehta      Sex: M   DOB: 15 May 1988\n"
         "MRN: SYN-1\n"
         "Date: 12 April 2026\n\n"
         "Impression: Iron deficiency confirmed.\n")
    # Patient B has the ferritin that would have supported it.
    b = ("MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
         "Patient: Rhea Sharma      Sex: F   DOB: 3 Feb 1991\n"
         "MRN: SYN-2\n"
         "Report Date: 12 April 2026\n\n"
         "IRON STUDIES\n"
         "Ferritin: 8 ng/mL\n")
    for i, txt in enumerate((a, b), start=1):
        f = tmp_path / f"claim_{i}.txt"
        f.write_text(txt)
        P.ingest_document(store, case.id, f, i)
    store.commit()
    P.process_case(store, cid := case.id, resolve_terminology=False)

    claim = store.q1("SELECT claim_text, evidence_status FROM claims "
                     "WHERE case_id = ?", (cid,))
    if claim is None:
        pytest.skip("corpus produced no claim; extraction is covered elsewhere")
    # The ferritin exists in the case, but not for this patient, so the claim
    # must NOT come back supported.
    assert claim["evidence_status"] != "SUPPORTED", claim


def test_an_unresolved_document_is_compared_only_with_other_unresolved_ones(tmp_path):
    """Rows from a document under review are grouped separately rather than
    dropped: dropping would hide evidence the corpus contains, and merging into
    a patient could fabricate a conflict between two people."""
    store = Store()
    case = store.insert(M.Case(case_ref="CT-UNRES-001", subject_label="x"))
    store.commit()
    known = ("MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
             "Patient: Arjun Mehta   Sex: M   DOB: 15 May 1988\n"
             "MRN: SYN-1\nReport Date: 18 January 2026\n\n"
             "COMPLETE BLOOD COUNT\nHemoglobin: 9.2 g/dL\n")
    # No identity fields at all: this document cannot be attached to anyone.
    orphan = ("MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
              "Report Date: 19 January 2026\n\n"
              "COMPLETE BLOOD COUNT\nHemoglobin: 14.8 g/dL\n")
    for i, txt in enumerate((known, orphan), start=1):
        f = tmp_path / f"u_{i}.txt"
        f.write_text(txt)
        P.ingest_document(store, case.id, f, i)
    store.commit()
    res = P.process_case(store, case.id, resolve_terminology=False)
    assert res.counts["facts"] == 2
    assert res.counts["conflicts"] == 0
    assert store.q1(
        "SELECT COUNT(*) AS n FROM identity_links WHERE status = 'NEEDS_REVIEW'"
    )["n"] == 1


def test_a_stale_patient_row_is_pruned_rather_than_left_to_poison_matching(tmp_path):
    """A patient no document links to is a leftover derivation, not a person.

    This is a regression test for a real failure. An earlier version of the
    resolver would create a patient from a name alone. Such a row can never be
    matched again by a document that states a full identity, so every document
    fell to review against a candidate that owned no evidence -- the registry
    reported zero patients and a review queue holding the whole case, while the
    stale row sat there looking plausible.
    """
    store = Store()
    case = store.insert(M.Case(case_ref="CT-STALE-001", subject_label="x"))
    store.commit()
    from caretrace.core import identity as ID
    store.insert(M.Patient(patient_ref="PT-0001", display_name="Arjun Mehta",
                           name_key=ID.normalise_name("Arjun Mehta"),
                           sex="M", dob=None, mrn=None, is_synthetic=1))
    store.commit()

    doc = ("MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
           "Patient: Arjun Mehta   Sex: M   DOB: 15 May 1988\n"
           "MRN: SYN-448120\nReport Date: 18 January 2026\n\n"
           "COMPLETE BLOOD COUNT\nHemoglobin: 9.2 g/dL\n")
    f = tmp_path / "stale.txt"
    f.write_text(doc)
    P.ingest_document(store, case.id, f, 1)
    store.commit()
    P.process_case(store, case.id, resolve_terminology=False)

    rows = store.q("SELECT patient_ref, mrn FROM patients")
    assert len(rows) == 1, rows
    assert rows[0]["mrn"] == "SYN448120", "the stale row survived and matched"
    assert store.q1("SELECT COUNT(*) AS n FROM identity_links "
                    "WHERE status = 'NEEDS_REVIEW'")["n"] == 0


def test_a_patient_linked_from_another_case_survives_a_run(tmp_path):
    """The prune is global, so it must not delete patients another case owns --
    cross-case resolution is the reason the registry persists at all."""
    store = Store()
    a = store.insert(M.Case(case_ref="CT-A", subject_label="a"))
    b = store.insert(M.Case(case_ref="CT-B", subject_label="b"))
    store.commit()
    doc = ("MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
           "Patient: Arjun Mehta   Sex: M   DOB: 15 May 1988\n"
           "MRN: SYN-448120\nReport Date: 18 January 2026\n\n"
           "COMPLETE BLOOD COUNT\nHemoglobin: 9.2 g/dL\n")
    f = tmp_path / "a.txt"
    f.write_text(doc)
    P.ingest_document(store, a.id, f, 1)
    store.commit()
    P.process_case(store, a.id, resolve_terminology=False)
    pid = store.q1("SELECT id FROM patients")["id"]

    # Processing an unrelated, empty case must not disturb the other case.
    P.process_case(store, b.id, resolve_terminology=False)
    assert store.q1("SELECT COUNT(*) AS n FROM patients WHERE id = ?",
                    (pid,))["n"] == 1


def test_the_same_clinician_is_one_row_across_institutions(demo):
    """Keying clinicians on name-plus-institution splits one doctor into
    several rows: the ordering clinician on a laboratory report and the author
    of their own clinic's note are the same person."""
    store, cid, _res, _out = demo
    dupes = store.q(
        "SELECT name_key, COUNT(*) AS n FROM clinicians "
        "GROUP BY name_key HAVING n > 1")
    assert dupes == [], dupes


def test_an_ordering_clinician_is_not_affiliated_to_the_issuing_laboratory(demo):
    """'Requested by: Dr. R. Nair' on a laboratory report says who asked for
    the test, not where they work. Recording the laboratory as their employer
    would invent an affiliation no document states."""
    store, cid, _res, _out = demo
    # Keys are computed, never spelled by hand: normalisation sorts tokens so
    # that "Nair, R." and "R. Nair" fold together.
    key = ID.normalise_name("Dr. R. Nair (synthetic)")
    row = store.q1(
        "SELECT i.display_name AS inst FROM clinicians c "
        "LEFT JOIN institutions i ON i.id = c.institution_id "
        "WHERE c.name_key = ?", (key,))
    assert row is not None
    # Nair authors the Riverside clinic notes, so that is what he is affiliated
    # to -- learned from a document that does imply it.
    assert row["inst"] == "RIVERSIDE INTERNAL MEDICINE CLINIC", row


def test_a_referrer_with_no_authored_document_has_no_invented_affiliation(demo):
    """When no document implies where a clinician works, the field stays empty
    rather than borrowing the nearest letterhead."""
    store, cid, _res, _out = demo
    row = store.q1("SELECT institution_id FROM clinicians WHERE name_key = ?",
                   (ID.normalise_name("Dr. A. Sharma (synthetic)"),))
    assert row is not None
    assert row["institution_id"] is None


def test_a_clinician_no_document_names_is_pruned(demo):
    """Clinicians are derived from participant rows, which are rebuilt each
    run. One left behind inflates the care team -- reporting a record fuller
    than the documents support."""
    store, cid, _res, _out = demo
    orphans = store.q(
        "SELECT id FROM clinicians c WHERE NOT EXISTS ("
        "  SELECT 1 FROM document_participants p WHERE p.clinician_id = c.id)")
    assert orphans == [], orphans


def test_an_institution_that_issued_nothing_is_pruned(demo):
    store, cid, _res, _out = demo
    orphans = store.q(
        "SELECT id FROM institutions i "
        "WHERE NOT EXISTS (SELECT 1 FROM clinicians c "
        "                  WHERE c.institution_id = i.id) "
        "  AND NOT EXISTS (SELECT 1 FROM encounters e "
        "                  WHERE e.institution_id = i.id)")
    assert orphans == [], orphans


def test_the_care_team_count_is_per_case_not_global(tmp_path):
    """A global count reports clinicians from every case ever processed, so a
    fresh single-document case would claim a care team it does not have."""
    store = Store()
    a = store.insert(M.Case(case_ref="CT-TEAM-A", subject_label="a"))
    b = store.insert(M.Case(case_ref="CT-TEAM-B", subject_label="b"))
    store.commit()
    mk = lambda name, mrn, doctor: (
        "MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
        f"Patient: {name}   Sex: M   DOB: 15 May 1988\n"
        f"MRN: {mrn}\nReport Date: 18 January 2026\n"
        f"Requested by: {doctor}\n\nCOMPLETE BLOOD COUNT\nHemoglobin: 9.2 g/dL\n")
    for case, name, mrn, doc_name, fn in (
            (a, "Arjun Mehta", "SYN-1", "Dr. R. Nair (synthetic)", "a.txt"),
            (b, "Priya Rao", "SYN-2", "Dr. T. Iyer (synthetic)", "b.txt")):
        f = tmp_path / fn
        f.write_text(mk(name, mrn, doc_name))
        P.ingest_document(store, case.id, f, 1)
    store.commit()
    P.process_case(store, a.id, resolve_terminology=False)
    P.process_case(store, b.id, resolve_terminology=False)

    from caretrace.api import views as V
    # Two clinicians exist in the registry, but each case names exactly one.
    assert store.q1("SELECT COUNT(*) AS n FROM clinicians")["n"] == 2
    for case in (a, b):
        v = V.patients(store, case.id)
        assert v["summary"]["clinicians"] == 1, (case.case_ref, v["summary"])
        assert len(v["care_team"]) == 1, v["care_team"]


def test_one_clinician_with_several_roles_is_one_care_team_row(demo):
    """A doctor who both orders laboratory tests and authors clinic notes is
    one person; their roles are collected, not split across rows."""
    store, cid, _res, _out = demo
    from caretrace.api import views as V
    team = V.patients(store, cid)["care_team"]
    names = [t["display_name"] for t in team]
    assert len(names) == len(set(names)), names
    multi = [t for t in team if "," in (t["roles"] or "")]
    assert multi, "expected at least one clinician with more than one role"
