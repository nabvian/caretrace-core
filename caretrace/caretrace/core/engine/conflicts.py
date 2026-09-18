"""Conflict detection.

CARETRACE never selects a winning value. A conflict is recorded with both
sides, both provenance chains, and resolution status UNRESOLVED. Nothing in
this module ranks one document as more correct than another.

Two families are implemented:

  * numeric conflicts     — same concept, overlapping clinical episode,
                            materially different values
  * medication conflicts  — a drug documented active in one record and absent
                            from a reconciliation list covering the same period
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Iterable, Optional

from .. import normalize as N
from ..models import (Conflict, ConflictType, Fact, Medication, Relationship,
                      RelType, Status)
from ...packs.medical import lexicon as LX


def _d(iso: Optional[str]) -> Optional[date]:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None


def _episode_clusters(group: list[Fact], window: int) -> list[list[Fact]]:
    """Single-link clustering of facts into episodes by observation date.

    Consecutive records within `window` days of each other belong to the same
    episode. This is what makes 'the record cannot have it both ways about the
    same moment' computable without hard-coding an episode calendar.
    """
    clusters: list[list[Fact]] = []
    for f in sorted(group, key=lambda x: (x.obs_date or "", x.id)):
        fd = _d(f.obs_date)
        if fd is None:
            continue
        if clusters:
            prev = _d(clusters[-1][-1].obs_date)
            if prev is not None and (fd - prev).days <= window:
                clusters[-1].append(f)
                continue
        clusters.append([f])
    return clusters


def detect_numeric_conflicts(
        facts: list[Fact],
        doc_of: Callable[[Fact], Optional[str]],
) -> tuple[list[Conflict], list[Relationship]]:
    """Same concept + same clinical episode + materially different values.

    `doc_of` maps a fact to the document it came from; records restated within
    one document are duplicates, not contradictions.

    Facts are first clustered into episodes by date, then each episode is
    partitioned into value groups. One conflict is emitted per pair of value
    groups, NOT per pair of facts — a value restated across four documents is
    one disagreement with four sources, not six separate findings. Every
    contributing record is kept in the member lists and gets its own
    CONTRADICTS relationship, so nothing loses provenance.

    A value that moves across a longer interval than the episode window is a
    documented change, handled by the change engine.

    Neither side is preferred and the conflict is left UNRESOLVED.
    """
    conflicts: list[Conflict] = []
    rels: list[Relationship] = []

    by_concept: dict[str, list[Fact]] = {}
    for f in facts:
        if f.value_num is not None and f.obs_date:
            by_concept.setdefault(f.concept, []).append(f)

    for concept, group in by_concept.items():
        cd = LX.CONCEPTS.get(concept)
        window = LX.conflict_window_days(concept)
        label = LX.concept_label(concept)
        threshold = (f"{cd.material_abs:g} {cd.canonical_unit} or "
                     f"{cd.material_rel * 100:g}% relative") if cd else "any difference"

        for episode in _episode_clusters(group, window):
            if len(episode) < 2:
                continue
            # Partition the episode into value groups: two facts share a group
            # when they are NOT materially different from each other.
            groups: list[list[Fact]] = []
            for f in episode:
                for g in groups:
                    if not N.material_difference(concept, g[0].value_num, f.value_num):
                        g.append(f)
                        break
                else:
                    groups.append([f])
            if len(groups) < 2:
                continue

            groups.sort(key=lambda g: (g[0].obs_date or "", g[0].id))
            for i, ga in enumerate(groups):
                for gb in groups[i + 1:]:
                    # A pair of groups that only ever appears within one
                    # document is a restatement inside that document.
                    docs_a = {doc_of(f) for f in ga}
                    docs_b = {doc_of(f) for f in gb}
                    if len(docs_a | docs_b) < 2:
                        continue

                    rep_a = min(ga, key=lambda f: (f.obs_date or "", f.id))
                    rep_b = min(gb, key=lambda f: (f.obs_date or "", f.id))
                    unit = rep_a.unit or rep_b.unit or ""
                    n_a, n_b = len(ga), len(gb)
                    extra = ""
                    if n_a > 1 or n_b > 1:
                        extra = (f" The values are restated across "
                                 f"{len(docs_a | docs_b)} documents "
                                 f"({n_a} record(s) on one side, {n_b} on the other); "
                                 f"all are listed as sources.")
                    conflicts.append(Conflict(
                        case_id=rep_a.case_id,
                        display_id="",  # assigned by the pipeline
                        conflict_type=ConflictType.NUMERIC_OBSERVATION,
                        concept=concept,
                        concept_label=label,
                        left_type="fact", left_id=rep_a.id,
                        right_type="fact", right_id=rep_b.id,
                        left_summary=f"{rep_a.value_num:g} {unit}".strip(),
                        right_summary=f"{rep_b.value_num:g} {unit}".strip(),
                        left_member_ids=[f.id for f in ga],
                        right_member_ids=[f.id for f in gb],
                        basis=(f"Source documents record different {label} values "
                               f"for the same episode (records within {window} "
                               f"day(s) of each other). Materiality threshold: "
                               f"{threshold}. CARETRACE does not select between "
                               f"them.{extra}"),
                        delta=round(rep_b.value_num - rep_a.value_num, 6),
                        status=Status.UNRESOLVED,
                    ))
                    # One relationship per cross-group pair of records, so the
                    # evidence graph shows every contradicting document.
                    for fa in ga:
                        for fb in gb:
                            if doc_of(fa) == doc_of(fb):
                                continue
                            rels.append(Relationship(
                                case_id=fa.case_id, rel_type=RelType.CONTRADICTS,
                                from_type="fact", from_id=fa.id,
                                to_type="fact", to_id=fb.id,
                                detail=(f"Different documented {label} values "
                                        f"within the same {window}-day window."),
                                status=Status.UNRESOLVED,
                            ))
    return conflicts, rels


def detect_status_conflicts(
        facts: list[Fact],
        doc_of: Callable[[Fact], Optional[str]],
) -> tuple[list[Conflict], list[Relationship]]:
    """Same qualitative finding, same episode, mutually exclusive value classes.

    Imaging, ECG, EEG and molecular reports state most of their result as text.
    Two documents saying 'no acute infarct' and 'acute infarct' about the same
    study period disagree exactly as plainly as two different haemoglobin
    numbers do, so they are surfaced the same way.

    Equality is on the pack's declared value class, not on the wording. 'No
    acute infarct' and 'no infarct' are the same finding and do not conflict;
    'acute infarct' is a different class and does. This is what keeps the
    detector from reporting a synonym as a contradiction.

    Neither side is preferred and the conflict is left UNRESOLVED.
    """
    conflicts: list[Conflict] = []
    rels: list[Relationship] = []

    by_concept: dict[str, list[Fact]] = {}
    for f in facts:
        if f.value_key and f.obs_date:
            by_concept.setdefault(f.concept, []).append(f)

    for concept, group in by_concept.items():
        window = LX.conflict_window_days(concept)
        label = LX.concept_label(concept)

        for episode in _episode_clusters(group, window):
            if len(episode) < 2:
                continue
            # Partition by declared value class.
            groups: dict[str, list[Fact]] = {}
            for f in episode:
                groups.setdefault(f.value_key, []).append(f)
            if len(groups) < 2:
                continue

            keys = sorted(groups, key=lambda k: (groups[k][0].obs_date or "",
                                                 groups[k][0].id))
            for i, ka in enumerate(keys):
                for kb in keys[i + 1:]:
                    ga, gb = groups[ka], groups[kb]
                    docs_a = {doc_of(f) for f in ga}
                    docs_b = {doc_of(f) for f in gb}
                    # Restated within one document is not a contradiction
                    # between documents.
                    if len(docs_a | docs_b) < 2:
                        continue

                    rep_a = min(ga, key=lambda f: (f.obs_date or "", f.id))
                    rep_b = min(gb, key=lambda f: (f.obs_date or "", f.id))
                    la = LX.status_value_label(concept, ka)
                    lb = LX.status_value_label(concept, kb)
                    extra = ""
                    if len(ga) > 1 or len(gb) > 1:
                        extra = (f" The findings are restated across "
                                 f"{len(docs_a | docs_b)} documents "
                                 f"({len(ga)} record(s) on one side, "
                                 f"{len(gb)} on the other); all are listed "
                                 f"as sources.")
                    conflicts.append(Conflict(
                        case_id=rep_a.case_id,
                        display_id="",  # assigned by the pipeline
                        conflict_type=ConflictType.STATUS_STATEMENT,
                        concept=concept,
                        concept_label=label,
                        left_type="fact", left_id=rep_a.id,
                        right_type="fact", right_id=rep_b.id,
                        left_summary=la,
                        right_summary=lb,
                        left_member_ids=[f.id for f in ga],
                        right_member_ids=[f.id for f in gb],
                        basis=(f"Source documents state mutually exclusive "
                               f"findings for {label} within the same episode "
                               f"(records within {window} day(s) of each "
                               f"other): \u201c{la}\u201d versus \u201c{lb}\u201d. "
                               f"Both are documented statements; CARETRACE "
                               f"does not select between them.{extra}"),
                        delta=None,
                        status=Status.UNRESOLVED,
                    ))
                    for fa in ga:
                        for fb in gb:
                            if doc_of(fa) == doc_of(fb):
                                continue
                            rels.append(Relationship(
                                case_id=fa.case_id, rel_type=RelType.CONTRADICTS,
                                from_type="fact", from_id=fa.id,
                                to_type="fact", to_id=fb.id,
                                detail=(f"Mutually exclusive documented {label} "
                                        f"findings within the same "
                                        f"{window}-day window."),
                                status=Status.UNRESOLVED,
                            ))
    return conflicts, rels


def detect_medication_conflicts(
        medications: list[Medication],
        doc_of: Callable[[Medication], Optional[str]],
        doc_type_of: Callable[[Medication], Optional[str]],
        doc_label: Callable[[str], str],
        reconciliation_doc_types: Iterable[str] = ("MEDICATION_LIST",),
) -> tuple[list[Conflict], list[Relationship], list[Medication]]:
    """A drug documented ACTIVE in one record and absent from a later
    reconciliation list.

    CARETRACE does not infer that the medication was stopped, and does not
    infer that the list is wrong. Absence is recorded as a DOCUMENTATION
    conflict because the uploaded records do not state what happened.

    Returns (conflicts, relationships, medications implicated) — the third
    value feeds the medication evidence-gap rule.
    """
    conflicts: list[Conflict] = []
    rels: list[Relationship] = []
    implicated: list[Medication] = []

    recon = [m for m in medications
             if doc_type_of(m) in tuple(reconciliation_doc_types)]
    if not recon:
        return conflicts, rels, implicated

    lists_by_doc: dict[str, list[Medication]] = {}
    for m in recon:
        did = doc_of(m)
        if did:
            lists_by_doc.setdefault(did, []).append(m)

    for doc_id, listed in lists_by_doc.items():
        list_date = next((m.record_date for m in listed if m.record_date), None)
        present = {m.drug_norm for m in listed}
        ld = _d(list_date)

        # Collect every unreconciled record, grouped by drug: the same drug
        # prescribed twice is ONE documentation conflict against this list,
        # evidenced by both prescriptions.
        by_drug: dict[str, list[Medication]] = {}
        for m in medications:
            if doc_of(m) == doc_id:
                continue
            if m.status != "ACTIVE" or m.drug_norm in present:
                continue
            if m.stop_date:
                continue  # the record documents a stop; nothing unexplained
            md = _d(m.record_date)
            if md and ld and md > ld:
                continue  # documented after the list was compiled
            by_drug.setdefault(m.drug_norm, []).append(m)

        for drug_norm in sorted(by_drug):
            group = sorted(by_drug[drug_norm],
                           key=lambda m: (m.record_date or "", m.id))
            rep = group[-1]  # most recent record documenting it as active
            implicated.append(rep)
            dates = ", ".join(m.record_date or "undated" for m in group)
            conflicts.append(Conflict(
                case_id=rep.case_id,
                display_id="",
                conflict_type=ConflictType.MEDICATION_DOCUMENTATION,
                concept=rep.drug_norm,
                concept_label=rep.drug_name,
                left_type="medication", left_id=rep.id,
                right_type="document", right_id=doc_id,
                left_summary=f"{rep.drug_name} — documented active ({dates})",
                right_summary=f"{rep.drug_name} — not listed on {doc_label(doc_id)}",
                left_member_ids=[m.id for m in group],
                right_member_ids=[doc_id],
                basis=("A medication documented as active in one or more records "
                       "does not appear on a later medication list, and no stop "
                       "date is documented. CARETRACE does not infer that it was "
                       "stopped, and does not infer that the list is wrong."),
                delta=None,
                status=Status.UNRESOLVED,
            ))
            for m in group:
                rels.append(Relationship(
                    case_id=m.case_id, rel_type=RelType.CONTRADICTS,
                    from_type="medication", from_id=m.id,
                    to_type="document", to_id=doc_id,
                    detail="Active medication absent from a later medication list.",
                    status=Status.UNRESOLVED,
                ))
    return conflicts, rels, implicated
