"""Identity resolution: what merges, what refuses, and why.

`identity.resolve` is a pure function over (assertion, registry rows), which is
what makes this file possible: every rule and every refusal is exercised
directly, with no database and no pipeline.

The bias under test is asymmetric on purpose. A missed merge leaves a document
in a review queue where a human sees it. A wrong merge produces a fully
provenanced record of a person who does not exist, and nothing downstream can
detect it -- the audit engine would find no conflict, because from its point of
view the record agrees with itself. So every ambiguous case here asserts a
refusal, not a best guess.
"""
from __future__ import annotations

import pytest

from caretrace.core import identity as ID


def _p(ref, name, dob=None, sex=None, mrn=None):
    """A registry row as `resolve` reads it."""
    return {"id": f"id-{ref}", "patient_ref": ref, "display_name": name,
            "name_key": ID.normalise_name(name), "dob": dob, "sex": sex,
            "mrn": ID.normalise_mrn(mrn)}


def _a(name=None, dob=None, sex=None, mrn=None):
    return ID.IdentityAssertion(raw_name=name, raw_dob=dob, raw_sex=sex,
                                raw_mrn=mrn)


ARJUN = _p("PT-0001", "Arjun Mehta", "1988-05-15", "M", "SYN-448120")


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("raw", [
    "Arjun Mehta", "ARJUN MEHTA", "arjun  mehta", "Mr. Arjun Mehta",
    "Mehta, Arjun", "Arjun Mehta (synthetic)", "Árjun Mehta",
])
def test_documented_name_variants_fold_to_one_key(raw):
    """Case, honorifics, diacritics, punctuation and word order all vary
    between clerks writing the same name, and none of it is identifying."""
    assert ID.normalise_name(raw) == "arjun mehta"


def test_different_people_do_not_fold_together():
    assert ID.normalise_name("Arjun Mehta") != ID.normalise_name("Anjun Mehta")
    assert ID.normalise_name("Arjun Mehta") != ID.normalise_name("Arjun Malhotra")


@pytest.mark.parametrize("raw,iso", [
    ("1988-05-15", "1988-05-15"),
    ("15 May 1988", "1988-05-15"),
    ("15-May-1988", "1988-05-15"),
    ("May 15, 1988", "1988-05-15"),
    ("15/05/1988", "1988-05-15"),   # 15 cannot be a month, so unambiguous
    ("15 May 88", "1988-05-15"),    # two-digit year windowed to the past
])
def test_documented_dates_parse(raw, iso):
    assert ID.normalise_dob(raw) == iso


@pytest.mark.parametrize("raw", ["03/04/1988", "04-03-88", "1988", "next Tuesday", ""])
def test_ambiguous_or_unparseable_dates_are_refused(raw):
    """An ambiguous date is returned as None, never guessed.

    03/04/1988 is two different days depending on who wrote it. Guessing would
    be worse than refusing, because matching would then act on the guess.
    """
    assert ID.normalise_dob(raw) is None


def test_absent_sex_is_not_a_value():
    """None means 'the document did not say', which must never match anything."""
    assert ID.normalise_sex(None) is None
    assert ID.normalise_sex("") is None
    assert ID.normalise_sex("unknown") is None


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #

def test_identity_is_read_from_a_packed_header_line():
    """Real headers put several fields on one line; all must be found."""
    text = ("MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n"
            "Patient: Arjun Mehta          Sex: M     DOB: 15 May 1988\n"
            "Case Ref: CT-DEMO-001         MRN: SYN-448120\n")
    a = ID.extract_identity(text)
    assert a.raw_name == "Arjun Mehta"
    assert a.dob == "1988-05-15"
    assert a.sex == "M"
    assert a.mrn == "SYN448120"


def test_a_name_in_the_body_is_not_an_identity_claim():
    """Identity is asserted in a header. A name mentioned in prose is not this
    document's subject, and reading it as one would attach the document to the
    wrong person."""
    text = ("RIVERSIDE INTERNAL MEDICINE CLINIC\n"
            "Patient: Arjun Mehta      MRN: SYN-448120\n"
            + "\n" * 14 +
            "Discussed the results with the patient's brother, Patient: Ravi Mehta\n")
    a = ID.extract_identity(text)
    assert a.raw_name == "Arjun Mehta"


# --------------------------------------------------------------------------- #
# Rules that merge
# --------------------------------------------------------------------------- #

def test_exact_mrn_match_links():
    r = ID.resolve(_a("Arjun Mehta", mrn="SYN-448120"), [ARJUN])
    assert r.status == ID.LinkStatus.LINKED
    assert r.basis == ID.Basis.MRN_EXACT
    assert r.patient_id == ARJUN["id"]


def test_mrn_matches_across_punctuation_variants():
    """SYN-448120 and syn448120 are the same identifier written twice."""
    r = ID.resolve(_a("Arjun Mehta", mrn="syn448120"), [ARJUN])
    assert r.status == ID.LinkStatus.LINKED


def test_full_demographic_triple_links_without_an_mrn():
    r = ID.resolve(_a("Mehta, Arjun", dob="15 May 1988", sex="M"), [ARJUN])
    assert r.status == ID.LinkStatus.LINKED
    assert r.basis == ID.Basis.NAME_DOB_SEX


def test_absent_sex_on_the_registry_is_not_a_disagreement():
    """A field the registry never recorded cannot contradict a document."""
    p = _p("PT-0002", "Rhea Sharma", "1991-02-03", sex=None)
    r = ID.resolve(_a("Rhea Sharma", dob="1991-02-03", sex="F"), [p])
    assert r.status == ID.LinkStatus.LINKED
    assert r.basis == ID.Basis.NAME_DOB


# --------------------------------------------------------------------------- #
# Rules that refuse. These are the point of the module.
# --------------------------------------------------------------------------- #

def test_the_deliberate_near_miss_pair_lands_in_review():
    """Two people, one character apart in the name, same date of birth.

    This is the case the whole design exists for: 'Arjun Mehta' and 'Anjun
    Mehta' born the same day are either a transcription error or two people,
    and the records do not say which. Merging would fabricate one person;
    CARETRACE queues it and shows the reviewer both candidates.
    """
    r = ID.resolve(_a("Anjun Mehta", dob="15 May 1988", sex="M"), [ARJUN])
    assert r.status == ID.LinkStatus.NEEDS_REVIEW
    assert r.patient_id is None
    assert r.candidates and r.candidates[0]["patient_ref"] == "PT-0001"
    assert "date of birth matches" in r.candidates[0]["why"]


def test_same_mrn_different_name_is_a_conflict_not_a_merge():
    """An MRN collision is a contradiction in the records themselves. It is
    exposed, exactly like a conflicting laboratory value, not resolved."""
    r = ID.resolve(_a("Priya Nair", dob="1979-11-02", mrn="SYN-448120"), [ARJUN])
    assert r.status == ID.LinkStatus.NEEDS_REVIEW
    assert r.basis == ID.Basis.MRN_CONFLICT
    assert "disagree" in r.rationale


def test_name_alone_never_merges():
    """However distinctive a name looks, it is not an identifier."""
    r = ID.resolve(_a("Arjun Mehta"), [ARJUN])
    assert r.status == ID.LinkStatus.NEEDS_REVIEW
    assert r.patient_id is None


def test_a_single_word_name_never_merges_even_with_a_matching_dob():
    """Shared surnames within a family plus one transcription error is a
    realistic route to a wrong merge, so one token is never enough."""
    r = ID.resolve(_a("Mehta", dob="15 May 1988"), [ARJUN])
    assert r.status == ID.LinkStatus.NEEDS_REVIEW
    assert r.basis == ID.Basis.INSUFFICIENT_IDENTITY


def test_two_equally_good_matches_are_never_broken_by_a_tiebreak():
    """A tiebreak here is a coin flip over whose records get combined."""
    twin = _p("PT-0009", "Arjun Mehta", "1988-05-15", "M", None)
    r = ID.resolve(_a("Arjun Mehta", dob="1988-05-15", sex="M"),
                   [ARJUN, twin])
    assert r.status == ID.LinkStatus.NEEDS_REVIEW
    assert r.basis == ID.Basis.AMBIGUOUS
    assert len(r.candidates) == 2


def test_conflicting_sex_with_matching_name_and_dob_is_review():
    r = ID.resolve(_a("Arjun Mehta", dob="1988-05-15", sex="F"), [ARJUN])
    assert r.status == ID.LinkStatus.NEEDS_REVIEW


def test_a_document_stating_no_identity_is_queued_not_dropped():
    r = ID.resolve(_a(), [ARJUN])
    assert r.status == ID.LinkStatus.NEEDS_REVIEW
    assert r.basis == ID.Basis.NO_IDENTITY_STATED


def test_an_unreadable_page_is_reported_as_unreadable_not_as_silent():
    """A scan may name the patient in ink. Saying it 'states no name' would be
    a false claim about the document, and the reviewer's next action differs:
    supply a text layer, versus find the identity elsewhere."""
    r = ID.resolve(_a(), [ARJUN], has_text=False)
    assert r.basis == ID.Basis.NO_READABLE_TEXT
    assert "cannot read" in r.rationale


def test_a_new_patient_needs_identity_strong_enough_to_rematch():
    """A registry row holding only a name can never be re-identified by a later
    document, so it would fragment the record rather than assemble it."""
    weak = ID.resolve(_a("Kiran Rao"), [])
    assert weak.status == ID.LinkStatus.NEEDS_REVIEW
    assert weak.basis == ID.Basis.INSUFFICIENT_IDENTITY

    strong = ID.resolve(_a("Kiran Rao", dob="2 Feb 1990"), [])
    assert strong.status == ID.LinkStatus.NEW_PATIENT


def test_every_refusal_states_a_reason_a_reviewer_can_act_on():
    """A review queue with no rationale is a pile of work with no entry point."""
    for r in (ID.resolve(_a("Anjun Mehta", dob="15 May 1988"), [ARJUN]),
              ID.resolve(_a("Arjun Mehta"), [ARJUN]),
              ID.resolve(_a(), [ARJUN]),
              ID.resolve(_a("Priya Nair", mrn="SYN-448120"), [ARJUN])):
        assert r.status == ID.LinkStatus.NEEDS_REVIEW
        assert len(r.rationale) > 40, r.rationale
        assert r.rationale.rstrip().endswith((".", "review."))
