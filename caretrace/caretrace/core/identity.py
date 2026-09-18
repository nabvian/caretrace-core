"""Patient identity: what a document asserted, and who the registry links it to.

Two rules govern this module, and they are the same rule twice.

**A wrong merge is the worst failure available here.** Attaching one person's
records to another produces a record that is internally consistent, fully
provenanced, and wrong -- the audit engine downstream would find no conflict at
all, because from its point of view there is nothing to disagree with. That is
strictly worse than an unresolved document, which is visible. So resolution is
deterministic, narrow, and refuses: anything short of a rule it can state is
left NEEDS_REVIEW with the candidates it was choosing between.

**An assertion is evidence; a link is an inference.** The header text a document
carried is stored verbatim and never rewritten. Normalisation exists only to
compare, and a normalised value never replaces the documented one -- the same
separation the fact/claim boundary enforces elsewhere in CARETRACE.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

# --------------------------------------------------------------------------- #
# Normalisation. Used for comparison only, never for display.
# --------------------------------------------------------------------------- #

#: Honorifics and qualifiers that carry no identifying information. Stripped
#: for matching only; the documented name keeps them.
_TITLES = {"mr", "mrs", "ms", "miss", "master", "dr", "prof", "sri", "smt",
           "shri", "baby", "b/o", "c/o"}

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "md", "mbbs", "do", "phd", "dm",
             "ms", "mch", "frcp", "facs"}


def normalise_name(raw: Optional[str]) -> str:
    """Fold a documented name to a comparison key.

    Diacritics, case, punctuation, honorifics and ordering all vary between
    documents describing the same person, and none of that variation is
    identifying. Word order is discarded (sorted tokens) because "Mehta Arjun"
    and "Arjun Mehta" are the same name written by two clerks -- a genuinely
    common variation, not a near-miss.

    A single-token result is deliberately still returned; the caller decides
    whether one token is enough to act on. It is not.
    """
    if not raw:
        return ""
    s = unicodedata.normalize("NFKD", raw)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    # Parenthetical annotations ("(synthetic)") are metadata, not name parts.
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z\s]", " ", s)
    tokens = [t for t in s.split() if t and t not in _TITLES and t not in _SUFFIXES]
    return " ".join(sorted(tokens))


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def normalise_dob(raw: Optional[str]) -> Optional[str]:
    """Parse a documented date of birth to ISO, or return None.

    Returning None on an unrecognised format is deliberate. A date of birth
    guessed from an ambiguous string is worse than an absent one, because
    matching would then act on it: 03/04/1988 is two different people
    depending on which side of the Atlantic wrote it, so a bare numeric
    day/month pair is refused rather than assumed.
    """
    if not raw:
        return None
    s = raw.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return _iso(y, mo, d)
    # "15 May 1988" / "15 May 88" / "May 15 1988"
    m = re.fullmatch(r"(\d{1,2})[\s/-]+([A-Za-z]{3,})[\s/-]+(\d{2,4})", s)
    if m:
        d, mon, y = m.group(1), m.group(2)[:3].lower(), m.group(3)
        if mon in _MONTHS:
            return _iso(_year(y), _MONTHS[mon], int(d))
    m = re.fullmatch(r"([A-Za-z]{3,})[\s/-]+(\d{1,2}),?[\s/-]+(\d{2,4})", s)
    if m:
        mon, d, y = m.group(1)[:3].lower(), m.group(2), m.group(3)
        if mon in _MONTHS:
            return _iso(_year(y), _MONTHS[mon], int(d))
    # An unambiguous numeric date: the day must exceed 12, so the ordering is
    # decidable from the value itself. Anything else is refused on purpose.
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and b <= 12:
            return _iso(y, b, a)
        if b > 12 and a <= 12:
            return _iso(y, a, b)
    return None


def _year(y: str) -> int:
    n = int(y)
    if n >= 100:
        return n
    # A two-digit year is windowed against today: a birth date cannot be in
    # the future, so 88 is 1988 rather than 2088.
    cur = date.today().year
    return n + 2000 if n + 2000 <= cur else n + 1900


def _iso(y: int, m: int, d: int) -> Optional[str]:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def normalise_sex(raw: Optional[str]) -> Optional[str]:
    """Fold documented sex to M/F/O, or None when not stated.

    None is not 'unknown sex' -- it means the document did not say. That
    distinction matters because an absent field must never make two records
    look like a match on a field neither of them asserted.
    """
    if not raw:
        return None
    s = raw.strip().lower()
    if s in ("m", "male", "man", "boy"):
        return "M"
    if s in ("f", "female", "woman", "girl"):
        return "F"
    if s in ("o", "other", "x", "intersex"):
        return "O"
    return None


def normalise_mrn(raw: Optional[str]) -> Optional[str]:
    """Fold an MRN for comparison, preserving its alphanumeric content."""
    if not raw:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    return s or None


# --------------------------------------------------------------------------- #
# Extraction: what the document said about identity.
# --------------------------------------------------------------------------- #

_FIELD_PATTERNS = {
    "raw_name": [r"patient(?:\s*name)?\s*[:\-]\s*([^\n|]+?)(?:\s{2,}|\||$)",
                 r"\bname\s*[:\-]\s*([^\n|]+?)(?:\s{2,}|\||$)"],
    "raw_dob":  [r"\b(?:dob|d\.o\.b\.?|date of birth)\s*[:\-]\s*([^\n|]+?)(?:\s{2,}|\||$)"],
    "raw_sex":  [r"\b(?:sex|gender)\s*[:\-]\s*([^\n|,]+?)(?:\s{2,}|\||,|$)"],
    "raw_mrn":  [r"\b(?:mrn|m\.r\.n\.?|hospital no|hosp no|uhid|patient id)\s*[:\-]\s*([^\n|]+?)(?:\s{2,}|\||$)"],
}


@dataclass
class IdentityAssertion:
    """Identity as one document stated it, plus comparison keys.

    The raw_* fields are the document's own words. The rest are derived for
    matching, and carry no authority over the raw form.
    """
    raw_name: Optional[str] = None
    raw_dob: Optional[str] = None
    raw_sex: Optional[str] = None
    raw_mrn: Optional[str] = None

    @property
    def name_key(self) -> str:
        return normalise_name(self.raw_name)

    @property
    def dob(self) -> Optional[str]:
        return normalise_dob(self.raw_dob)

    @property
    def sex(self) -> Optional[str]:
        return normalise_sex(self.raw_sex)

    @property
    def mrn(self) -> Optional[str]:
        return normalise_mrn(self.raw_mrn)

    @property
    def is_empty(self) -> bool:
        return not any((self.raw_name, self.raw_dob, self.raw_mrn))

    def as_row(self) -> dict:
        return {"raw_name": self.raw_name, "raw_dob": self.raw_dob,
                "raw_sex": self.raw_sex, "raw_mrn": self.raw_mrn,
                "name_key": self.name_key, "dob": self.dob,
                "sex": self.sex, "mrn": self.mrn}


def extract_identity(text: str) -> IdentityAssertion:
    """Read identity fields from a document's text.

    Only the first page's header region is searched: identity is asserted in a
    header, whereas a name appearing in the body ("discussed with the patient's
    brother, Arjun") is not this document's subject. Restricting the window is
    what keeps a body mention from being read as an identity claim.
    """
    head = "\n".join(text.splitlines()[:14])
    out = IdentityAssertion()
    for field_name, patterns in _FIELD_PATTERNS.items():
        for pat in patterns:
            # MULTILINE matters: the patterns end at "two spaces, a pipe, or
            # end of line", and a header packs several fields onto one line.
            # Without it, `$` only matches the end of the whole header block
            # and every field except the last silently fails to extract.
            m = re.search(pat, head, re.IGNORECASE | re.MULTILINE)
            if m:
                val = m.group(1).strip(" \t:-|")
                if val:
                    setattr(out, field_name, val)
                    break
    return out


# --------------------------------------------------------------------------- #
# Resolution.
# --------------------------------------------------------------------------- #

class LinkStatus:
    LINKED = "LINKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NEW_PATIENT = "NEW_PATIENT"


class Basis:
    MRN_EXACT = "MRN_EXACT"
    NAME_DOB_SEX = "NAME_DOB_SEX"
    NAME_DOB = "NAME_DOB"
    NO_MATCH = "NO_MATCH"
    NO_IDENTITY_STATED = "NO_IDENTITY_STATED"
    NO_READABLE_TEXT = "NO_READABLE_TEXT"
    MRN_CONFLICT = "MRN_CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"
    INSUFFICIENT_IDENTITY = "INSUFFICIENT_IDENTITY"


@dataclass
class Resolution:
    """One resolution decision, with the reasoning it will be reviewed on."""
    status: str
    basis: str
    rationale: str
    patient_id: Optional[str] = None
    candidates: Optional[list[dict]] = None

    def candidates_json(self) -> Optional[str]:
        return json.dumps(self.candidates) if self.candidates else None


def resolve(assertion: IdentityAssertion,
            patients: Iterable[dict],
            has_text: bool = True) -> Resolution:
    """Decide which registry patient a document's assertion refers to.

    The rules, in order, each stated as the reviewer will read it:

    1. **An exact MRN match wins.** An MRN is issued by the institution to
       identify one person; it is the only field here that is designed for
       this job.
    2. **A same-MRN, different-person disagreement is a review, not a merge.**
       If the MRN matches but the documented name is a different name, that is
       a contradiction in the records themselves -- exactly the class of thing
       CARETRACE exposes rather than resolves.
    3. **Name plus date of birth plus sex, all three present and equal.**
    4. **Name plus date of birth, where the registry did not state a sex.**
       Absence of a field is not disagreement with it.
    5. **Anything else is NEEDS_REVIEW.** Name alone is never enough, however
       distinctive it looks -- and multiple equally good matches are never
       broken by a tiebreak, because a tiebreak here is a coin flip on which
       person's records get merged.
    """
    plist = list(patients)

    if assertion.is_empty:
        # Two different reasons produce an empty assertion, and they call for
        # different actions from the reviewer, so they are never reported as
        # one. A page with no text layer (a scan) may well state the patient's
        # name in ink -- CARETRACE simply cannot read it, and saying "states no
        # name" about such a page would be a false claim about the document.
        if not has_text:
            return Resolution(
                LinkStatus.NEEDS_REVIEW, Basis.NO_READABLE_TEXT,
                "No text could be extracted from this document, so no identity "
                "could be read from it. The document may well name a patient; "
                "CARETRACE cannot read it without a text layer. Queued for "
                "review.")
        return Resolution(
            LinkStatus.NEEDS_REVIEW, Basis.NO_IDENTITY_STATED,
            "This document's text states no patient name, date of birth or MRN "
            "in its header, so it cannot be attached to a patient. It is "
            "retained and queued for review rather than assigned.")

    # --- 1 & 2: MRN -------------------------------------------------------- #
    if assertion.mrn:
        mrn_hits = [p for p in plist if p.get("mrn") == assertion.mrn]
        if len(mrn_hits) == 1:
            p = mrn_hits[0]
            same_name = (not assertion.name_key or not p.get("name_key")
                         or assertion.name_key == p["name_key"])
            if same_name:
                return Resolution(
                    LinkStatus.LINKED, Basis.MRN_EXACT,
                    f"MRN {assertion.raw_mrn} matches registry patient "
                    f"{p['patient_ref']} exactly.", p["id"])
            return Resolution(
                LinkStatus.NEEDS_REVIEW, Basis.MRN_CONFLICT,
                f"MRN {assertion.raw_mrn} matches registry patient "
                f"{p['patient_ref']}, but this document names "
                f"'{assertion.raw_name}' where the registry holds "
                f"'{p['display_name']}'. The records disagree about who this "
                f"MRN belongs to; CARETRACE does not choose between them.",
                candidates=[_cand(p, "MRN matches, documented name differs")])
        if len(mrn_hits) > 1:
            return Resolution(
                LinkStatus.NEEDS_REVIEW, Basis.AMBIGUOUS,
                f"MRN {assertion.raw_mrn} matches {len(mrn_hits)} registry "
                f"patients, which should not occur. Queued for review rather "
                f"than resolved.",
                candidates=[_cand(p, "duplicate MRN in registry") for p in mrn_hits])

    # --- 3 & 4: demographic triple ----------------------------------------- #
    if assertion.name_key and assertion.dob:
        # A single-token name is not identifying enough to merge on, even with
        # a matching date of birth: shared surnames within a family plus a
        # transcription error is a realistic route to a wrong merge.
        if len(assertion.name_key.split()) < 2:
            near = [p for p in plist if p.get("dob") == assertion.dob]
            return Resolution(
                LinkStatus.NEEDS_REVIEW, Basis.INSUFFICIENT_IDENTITY,
                f"This document gives only a single-word name "
                f"('{assertion.raw_name}') with a date of birth. That is not "
                f"enough to attach records to a person, so it is queued for "
                f"review.",
                candidates=[_cand(p, "date of birth matches") for p in near])

        name_dob = [p for p in plist
                    if p.get("name_key") == assertion.name_key
                    and p.get("dob") == assertion.dob]
        if len(name_dob) == 1:
            p = name_dob[0]
            if assertion.sex and p.get("sex") and assertion.sex != p["sex"]:
                return Resolution(
                    LinkStatus.NEEDS_REVIEW, Basis.AMBIGUOUS,
                    f"Name and date of birth match registry patient "
                    f"{p['patient_ref']}, but the documented sex differs "
                    f"({assertion.sex} here, {p['sex']} on the registry). "
                    f"Queued for review.",
                    candidates=[_cand(p, "name and DOB match, sex differs")])
            basis = (Basis.NAME_DOB_SEX
                     if assertion.sex and p.get("sex") else Basis.NAME_DOB)
            detail = ("name, date of birth and sex all match"
                      if basis == Basis.NAME_DOB_SEX
                      else "name and date of birth match; sex is not stated on "
                           "both records, and an absent field is not treated as "
                           "a disagreement")
            return Resolution(
                LinkStatus.LINKED, basis,
                f"Matched registry patient {p['patient_ref']}: {detail}.",
                p["id"])
        if len(name_dob) > 1:
            return Resolution(
                LinkStatus.NEEDS_REVIEW, Basis.AMBIGUOUS,
                f"Name and date of birth match {len(name_dob)} registry "
                f"patients equally well. CARETRACE does not break the tie.",
                candidates=[_cand(p, "name and DOB match") for p in name_dob])

    # --- 5: refuse --------------------------------------------------------- #
    near = [p for p in plist
            if (assertion.name_key and p.get("name_key") == assertion.name_key)
            or (assertion.dob and p.get("dob") == assertion.dob)]
    if near:
        why = []
        for p in near:
            bits = []
            if assertion.name_key == p.get("name_key"):
                bits.append("name matches")
            if assertion.dob and assertion.dob == p.get("dob"):
                bits.append("date of birth matches")
            if assertion.dob and p.get("dob") and assertion.dob != p["dob"]:
                bits.append(f"date of birth differs ({assertion.dob} vs {p['dob']})")
            if not assertion.dob:
                bits.append("this document states no usable date of birth")
            why.append(_cand(p, ", ".join(bits) or "partial match"))
        return Resolution(
            LinkStatus.NEEDS_REVIEW, Basis.INSUFFICIENT_IDENTITY,
            "This document partially matches an existing patient but not on a "
            "rule strong enough to merge records. Attaching it on a partial "
            "match risks combining two people's records, so it is queued for "
            "review with the candidates listed.",
            candidates=why)

    # A patient record is created only from a document that states enough
    # identity to be matched AGAIN. A registry entry carrying nothing but a
    # name can never be re-identified by a later document -- it would sit there
    # accumulating nothing while every subsequent report queued for review, so
    # the record ends up more fragmented than if it had never been created.
    # Requiring an MRN, or a full name plus date of birth, is what makes
    # re-processing a corpus reproduce the same registry.
    creatable = bool(assertion.mrn) or bool(
        assertion.dob and len(assertion.name_key.split()) >= 2)
    if not creatable:
        stated = ", ".join(
            lbl for lbl, val in (("a name", assertion.raw_name),
                                 ("a date of birth", assertion.raw_dob),
                                 ("an MRN", assertion.raw_mrn)) if val)
        return Resolution(
            LinkStatus.NEEDS_REVIEW, Basis.INSUFFICIENT_IDENTITY,
            f"This document states {stated}, which is not enough to open a "
            f"patient record: no later document could be matched to it with "
            f"confidence. An MRN, or a full name with a date of birth, is "
            f"required. Queued for review.")

    return Resolution(
        LinkStatus.NEW_PATIENT, Basis.NO_MATCH,
        "No registry patient matches this document's stated identity, so a new "
        "patient record is created from it.")


def _cand(p: dict, why: str) -> dict:
    return {"patient_id": p["id"], "patient_ref": p.get("patient_ref"),
            "display_name": p.get("display_name"), "dob": p.get("dob"),
            "sex": p.get("sex"), "mrn": p.get("mrn"), "why": why}
