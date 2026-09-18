"""Building the registry: patients, institutions, clinicians, encounters.

This module turns per-document identity assertions into a link graph. It owns
no matching rules of its own -- those live in `identity.resolve`, which is a
pure function over (assertion, existing patients) so it can be tested exhaustively
without a database. Here we do the ordering, the writing, and the derivation.

One ordering decision matters: documents are resolved in ingestion order, and
each decision sees the patients created by earlier decisions. That makes the
result reproducible for a given corpus order, and it is why the review queue is
stable rather than depending on which document happened to be read first.
"""
from __future__ import annotations

import re
from typing import Optional

from . import identity as ID
from . import models as M
from .store import Store

# --------------------------------------------------------------------------- #
# Institutions and clinicians.
# --------------------------------------------------------------------------- #

#: Document labels that state a participant role, mapped to the role. Only
#: labelled participants are recorded: an unlabelled name on a page has no
#: documented role, and inventing one would be exactly the kind of guess this
#: product refuses to make.
_ROLE_LABELS: list[tuple[str, str]] = [
    (r"requested by",  M.ParticipantRole.ORDERING),
    (r"ordered by",    M.ParticipantRole.ORDERING),
    (r"referred by",   M.ParticipantRole.REFERRING),
    (r"referring(?: physician| doctor)?", M.ParticipantRole.REFERRING),
    (r"verified by",   M.ParticipantRole.PERFORMING),
    (r"reported by",   M.ParticipantRole.PERFORMING),
    (r"performed by",  M.ParticipantRole.PERFORMING),
    (r"consultant",    M.ParticipantRole.AUTHORING),
    (r"seen by",       M.ParticipantRole.AUTHORING),
    (r"attending",     M.ParticipantRole.AUTHORING),
]

_INSTITUTION_HINTS = ("hospital", "laboratory", "labs", "clinic", "centre",
                      "center", "diagnostics", "diagnostic", "imaging",
                      "genomics", "sciences", "pathology", "institute")

#: Words that name a KIND OF DOCUMENT. A line containing one is a title, not a
#: letterhead -- "CUMULATIVE LABORATORY SUMMARY" satisfies the institution
#: hints above purely by accident, and recording it as the issuer would put a
#: plausible-looking falsehood on the patient's record.
_DOCUMENT_WORDS = ("report", "summary", "note", "notes", "list", "letter",
                   "prescription", "count", "panel", "studies", "record",
                   "referral", "discharge", "consultation")


def extract_institution(text: str) -> Optional[str]:
    """Read the issuing institution from a document's letterhead.

    Only the first three lines are considered, and the line must look like a
    letterhead (predominantly upper case, or naming a recognisable institution
    kind). A hospital named in the body of a referral letter is the *destination*
    of that letter, not its issuer, so widening this window would systematically
    mis-attribute documents.
    """
    # The issuing line must NAME a kind of organisation. Requiring that, rather
    # than accepting any upper-case line, is what separates a letterhead from a
    # document title: "COMPLETE BLOOD COUNT" and "DISCHARGE SUMMARY" are also
    # upper case and also sit at the top of the page. The cost is that an
    # institution whose name carries no such word is not extracted -- a missing
    # institution, which is visible, rather than a document title recorded as
    # the issuer, which is wrong and looks fine.
    for line in text.splitlines()[:4]:
        s = line.strip()
        if len(s) < 4 or ":" in s:
            continue
        letters = [c for c in s if c.isalpha()]
        if not letters:
            continue
        low = s.lower()
        if any(w in low.split() or w in low.replace("-", " ").split()
               for w in _DOCUMENT_WORDS):
            continue
        if any(h in low for h in _INSTITUTION_HINTS):
            # Drop the synthetic-data marker; it is a property of the demo
            # corpus, not part of the institution's name.
            s = re.sub(r"\s*\((?:synthetic)\)\s*$", "", s, flags=re.IGNORECASE)
            if "SYNTHETIC RECORD" in s.upper() or "NOT A REAL" in s.upper():
                continue
            return s.strip()
    return None


def extract_participants(text: str) -> list[tuple[str, str]]:
    """Return (role, documented clinician name) pairs found in a document.

    Matching is anchored on the document's own label, so the role is something
    the record states rather than something inferred from where a name sits on
    the page.
    """
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for label, role in _ROLE_LABELS:
        for m in re.finditer(
                rf"\b{label}\s*[:\-]\s*([^\n|]+)", text, re.IGNORECASE):
            name = _clean_clinician(m.group(1))
            if not name:
                continue
            key = (role, ID.normalise_name(name))
            if key in seen:
                continue
            seen.add(key)
            out.append((role, name))
    return out


def _clean_clinician(raw: str) -> Optional[str]:
    """Trim a documented clinician name of trailing report metadata.

    Header lines pack several fields onto one row ("Requested by: Dr. R. Nair
    (synthetic)   Report No: LAB-26-00811"), so the name ends at the first
    run of two spaces or at a following "Field:" label.
    """
    s = re.split(r"\s{2,}|\s\|\s", raw.strip())[0]
    s = re.split(r"\b(?:report no|reg|modality|date|sample|ref)\b\s*[:.]",
                 s, flags=re.IGNORECASE)[0]
    # Qualifications follow a comma ("Dr. S. Kulkarni (synthetic), MD Pathology")
    # and are not part of the name.
    s = s.split(",")[0].strip(" \t:-.")
    if not s or not re.search(r"[A-Za-z]{2}", s):
        return None
    # A role label with no name after it ("Consultant Gastroenterologist") names
    # a speciality, not a person.
    if not re.search(r"\b(?:dr|prof|mr|ms|mrs)\b", s, re.IGNORECASE):
        return None
    return s


# --------------------------------------------------------------------------- #
# Registry construction.
# --------------------------------------------------------------------------- #

def _next_patient_ref(store: Store) -> str:
    row = store.q1("SELECT COUNT(*) AS n FROM patients")
    return f"PT-{(row['n'] if row else 0) + 1:04d}"


def _get_or_create_institution(store: Store, name: Optional[str]
                               ) -> Optional[str]:
    if not name:
        return None
    key = ID.normalise_name(name)
    if not key:
        return None
    row = store.q1("SELECT id FROM institutions WHERE name_key = ?", (key,))
    if row:
        return row["id"]
    inst = store.insert(M.Institution(display_name=name, name_key=key))
    return inst.id


#: Roles for which the letterhead DOES imply where the clinician works. A
#: laboratory's verifying pathologist and a clinic's consulting physician
#: practise at the issuing institution. An ordering or referring clinician does
#: not: "Requested by: Dr. R. Nair" on a laboratory report says Dr. Nair asked
#: for the test, and says nothing at all about where Dr. Nair works -- he is
#: typically at the clinic that sent the patient. Recording him as laboratory
#: staff would invent an affiliation no document states.
_AFFILIATING_ROLES = frozenset({M.ParticipantRole.PERFORMING,
                                M.ParticipantRole.AUTHORING})


def _get_or_create_clinician(store: Store, name: str,
                             institution_id: Optional[str]) -> Optional[str]:
    """Find or create a clinician, upgrading a known name with an affiliation.

    Matching is by name, not by name-plus-institution. Keying on the pair would
    split one doctor into several rows -- the same person appears as an ordering
    clinician with no stated affiliation on a laboratory report and as the
    author of their own clinic's note -- which defeats the purpose of having a
    clinician table at all.

    A row that already carries an institution is never reassigned to a
    different one: a genuine namesake at another institution is kept separate
    rather than silently merged, and the first affiliation observed stands.
    """
    key = ID.normalise_name(name)
    if not key:
        return None

    rows = store.q("SELECT id, institution_id FROM clinicians WHERE name_key = ?",
                   (key,))
    if institution_id is None:
        # Nothing to add: reuse any existing row for this name.
        if rows:
            return rows[0]["id"]
    else:
        for r in rows:
            if r["institution_id"] == institution_id:
                return r["id"]
        # Upgrade a row that has no affiliation yet rather than duplicating.
        for r in rows:
            if r["institution_id"] is None:
                store.conn.execute(
                    "UPDATE clinicians SET institution_id = ? WHERE id = ?",
                    (institution_id, r["id"]))
                return r["id"]
        # Same name, different institution: a possible namesake, kept apart.

    c = store.insert(M.Clinician(display_name=name, name_key=key,
                                 institution_id=institution_id))
    return c.id


def _prune_orphan_patients(store: Store) -> int:
    """Drop patient rows that no document anywhere links to.

    Patients are DERIVED from documents: a patient row exists because some
    document asserted that identity. Links are per-run derived rows, so after a
    reset a patient no link references is a leftover from an earlier run --
    holding no facts, no claims, and no documents.

    Leaving them is not harmless. A stale row still takes part in matching, and
    a row recording a weak identity (a name and nothing else, which earlier
    versions of this module would create) can never be matched again by a
    document stating a full identity. Every such document then falls to review
    against a candidate that owns no evidence: the registry reports zero
    patients and a review queue containing the entire case.

    The condition is deliberately global rather than per-case. A patient linked
    only from ANOTHER case's documents is real and cross-case resolution is the
    point of the registry, so it must survive a run over this case.
    """
    orphans = store.q(
        "SELECT p.id FROM patients p WHERE NOT EXISTS ("
        "  SELECT 1 FROM identity_links l WHERE l.patient_id = p.id)")
    for row in orphans:
        store.conn.execute("DELETE FROM patients WHERE id = ?", (row["id"],))
    return len(orphans)


def _prune_orphan_directory(store: Store) -> int:
    """Drop clinicians and institutions that nothing references any more.

    Same argument as the patient prune, and run at the END of the build rather
    than the start: participants are per-run derived rows, so a clinician is
    only genuinely orphaned once this run has finished writing them. Pruning
    first would delete rows this run is about to reference.

    A clinician with no participant row appears in no document. An institution
    with no clinician and no encounter issued nothing. Left in place they
    inflate the care-team count -- reporting a record fuller than the documents
    support, which is the failure mode this whole screen exists to avoid.
    """
    n = 0
    for row in store.q(
            "SELECT c.id FROM clinicians c WHERE NOT EXISTS ("
            "  SELECT 1 FROM document_participants p WHERE p.clinician_id = c.id)"):
        store.conn.execute("DELETE FROM clinicians WHERE id = ?", (row["id"],))
        n += 1
    for row in store.q(
            "SELECT i.id FROM institutions i "
            "WHERE NOT EXISTS (SELECT 1 FROM clinicians c "
            "                  WHERE c.institution_id = i.id) "
            "  AND NOT EXISTS (SELECT 1 FROM encounters e "
            "                  WHERE e.institution_id = i.id)"):
        store.conn.execute("DELETE FROM institutions WHERE id = ?", (row["id"],))
        n += 1
    return n


def build_registry(store: Store, case_id: str,
                   documents: list[M.Document],
                   pages_by_doc: dict[str, list[M.DocumentPage]],
                   is_synthetic: bool = True) -> dict:
    """Resolve identity for every document in a case and derive the link graph.

    Returns counts for the pipeline stage record. The registry itself
    (patients, institutions, clinicians) persists across runs and cases; the
    assertions, links and encounters written here are per-run derived rows and
    have already been cleared by the caller.
    """
    counts = {"patients_created": 0, "linked": 0, "needs_review": 0,
              "institutions": 0, "clinicians": 0, "participants": 0,
              "encounters": 0, "stale_patients_pruned": 0}

    counts["stale_patients_pruned"] = _prune_orphan_patients(store)

    for doc in documents:
        pages = pages_by_doc.get(doc.id) or []
        if not pages:
            continue
        first = pages[0].text
        full = "\n".join(p.text for p in pages)

        # ---- identity ---------------------------------------------------- #
        assertion = ID.extract_identity(first)
        row = store.insert(M.IdentityAssertionRow(
            case_id=case_id, document_id=doc.id, **assertion.as_row()))

        existing = store.q("SELECT * FROM patients")
        res = ID.resolve(assertion, existing,
                         has_text=bool(full.strip()))

        patient_id = res.patient_id
        if res.status == ID.LinkStatus.NEW_PATIENT:
            pat = store.insert(M.Patient(
                patient_ref=_next_patient_ref(store),
                display_name=(assertion.raw_name or "Unnamed subject").strip(),
                name_key=assertion.name_key, dob=assertion.dob,
                sex=assertion.sex, mrn=assertion.mrn,
                is_synthetic=is_synthetic))
            patient_id = pat.id
            counts["patients_created"] += 1
            # The link records NEW_PATIENT rather than LINKED so that a reader
            # can tell which document a patient record was created from.
            rationale = (f"{res.rationale} Created {pat.patient_ref} from this "
                         f"document.")
        else:
            rationale = res.rationale

        store.insert(M.IdentityLink(
            case_id=case_id, document_id=doc.id, assertion_id=row.id,
            status=res.status, basis=res.basis, rationale=rationale,
            patient_id=patient_id, candidates=res.candidates))

        if res.status == ID.LinkStatus.NEEDS_REVIEW:
            counts["needs_review"] += 1
        elif res.status == ID.LinkStatus.LINKED:
            counts["linked"] += 1

        # ---- institution and participants -------------------------------- #
        inst_name = extract_institution(first)
        inst_id = _get_or_create_institution(store, inst_name)

        for role, name in extract_participants(full):
            # Only roles the letterhead actually implies carry an affiliation.
            affil = inst_id if role in _AFFILIATING_ROLES else None
            clin_id = _get_or_create_clinician(store, name, affil)
            if not clin_id:
                continue
            try:
                store.insert(M.DocumentParticipant(
                    document_id=doc.id, role=role, clinician_id=clin_id,
                    raw_text=name))
                counts["participants"] += 1
            except Exception:
                # The (document, clinician, role) uniqueness constraint is the
                # intended dedupe: one person named twice under one role on one
                # document is one participation.
                pass

        # ---- encounter --------------------------------------------------- #
        # Grouping key is (patient, date, institution): two reports issued by
        # different institutions on one day are not one documented contact, and
        # merging them would invent a visit the records do not describe.
        if patient_id and doc.doc_date:
            enc = store.q1(
                "SELECT id FROM encounters WHERE case_id = ? AND patient_id = ? "
                "AND occurred_on = ? AND IFNULL(institution_id,'') = IFNULL(?,'')",
                (case_id, patient_id, doc.doc_date, inst_id))
            if enc:
                enc_id = enc["id"]
            else:
                enc_id = store.insert(M.Encounter(
                    case_id=case_id, patient_id=patient_id,
                    occurred_on=doc.doc_date, institution_id=inst_id)).id
                counts["encounters"] += 1
            store.conn.execute(
                "INSERT OR IGNORE INTO encounter_documents (encounter_id, "
                "document_id) VALUES (?, ?)", (enc_id, doc.id))

    store.commit()
    counts["stale_directory_pruned"] = _prune_orphan_directory(store)
    store.commit()

    # Counted per case, not globally. A global count would grow with every case
    # ever processed and report a care team larger than the one in this record.
    counts["institutions"] = store.q1(
        "SELECT COUNT(DISTINCT i.id) AS n FROM institutions i "
        "JOIN clinicians c ON c.institution_id = i.id "
        "JOIN document_participants p ON p.clinician_id = c.id "
        "JOIN documents d ON d.id = p.document_id WHERE d.case_id = ?",
        (case_id,))["n"]
    counts["clinicians"] = store.q1(
        "SELECT COUNT(DISTINCT p.clinician_id) AS n FROM document_participants p "
        "JOIN documents d ON d.id = p.document_id WHERE d.case_id = ?",
        (case_id,))["n"]
    return counts
