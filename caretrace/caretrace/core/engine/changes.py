"""Change detection.

A documented change is: same normalized concept, different observation dates,
different values, in the record. It is a statement about the DOCUMENTS, not
about the patient — the wording used throughout is 'documented change'.

Duplicates (same concept, same date, same value) are recorded as DUPLICATES
relationships instead, and never counted as changes.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

from .. import normalize as N
from ..models import Change, Fact, Relationship, RelType, Status
from ...packs.medical import lexicon as LX


def _days_between(a_iso: str | None, b_iso: str | None) -> int:
    """Absolute day interval, or a large number when either date is unusable."""
    try:
        return abs((date.fromisoformat(b_iso) - date.fromisoformat(a_iso)).days)
    except (TypeError, ValueError):
        return 10 ** 6


def _sortable(f: Fact) -> tuple:
    return (f.obs_date or "9999-12-31", f.display_id or "", f.id)


def group_by_concept(facts: Iterable[Fact]) -> dict[str, list[Fact]]:
    out: dict[str, list[Fact]] = {}
    for f in facts:
        out.setdefault(f.concept, []).append(f)
    for k in out:
        out[k].sort(key=_sortable)
    return out


def _representatives(group: list[Fact]) -> dict[str, Fact]:
    """One representative fact per observation date.

    When several documents report the same concept on the same date, the
    highest-confidence record represents that date. This is a display choice
    about which row to draw the series through — it is NOT an adjudication:
    the other records remain in the store, keep their own provenance, and are
    still tested for conflict independently.
    """
    by_date: dict[str, Fact] = {}
    for f in group:
        if f.value_num is None or not f.obs_date:
            continue
        cur = by_date.get(f.obs_date)
        if cur is None or (f.confidence, f.id) > (cur.confidence, cur.id):
            by_date[f.obs_date] = f
    return by_date


def detect_duplicates(facts: list[Fact]) -> list[Relationship]:
    """Same concept + same date + same value, recorded in different documents."""
    rels: list[Relationship] = []
    by_key: dict[tuple, list[Fact]] = {}
    for f in facts:
        if f.value_num is None or not f.obs_date:
            continue
        by_key.setdefault((f.concept, f.obs_date, round(f.value_num, 6)), []).append(f)

    for (concept, obs_date, value), group in by_key.items():
        if len(group) < 2:
            continue
        group.sort(key=_sortable)
        primary = group[0]
        for other in group[1:]:
            rels.append(Relationship(
                case_id=primary.case_id,
                rel_type=RelType.DUPLICATES,
                from_type="fact", from_id=other.id,
                to_type="fact", to_id=primary.id,
                detail=(f"{LX.concept_label(concept)} {value:g} dated {obs_date} "
                        f"is recorded in more than one document."),
                status=Status.DOCUMENTED,
            ))
    return rels


def detect_changes(facts: list[Fact]) -> tuple[list[Change], list[Relationship]]:
    """Return (Change rows, CHANGED_FROM/CHANGED_TO relationships).

    A documented change is emitted between consecutive DISTINCT observation
    dates of the same concept whose values differ AND which fall in different
    clinical episodes, as defined by the pack's episode window.

    Two records inside the same episode are not a change over time: the record
    is saying two things about one moment. Those pairs belong to the conflict
    engine, and emitting them here as well would report a single disagreement
    twice under two different headings.

    The wording is deliberately neutral: a change describes the record, not the
    patient.
    """
    changes: list[Change] = []
    rels: list[Relationship] = []

    for concept, group in group_by_concept(facts).items():
        window = LX.conflict_window_days(concept)
        by_date = _representatives(group)
        series = [by_date[d] for d in sorted(by_date)]
        if len(series) < 2:
            continue
        for a, b in zip(series, series[1:]):
            if a.value_num == b.value_num:
                continue
            if _days_between(a.obs_date, b.obs_date) <= window:
                continue  # same episode — assessed as a conflict, not a change
            delta = round(b.value_num - a.value_num, 6)
            label = LX.concept_label(concept)
            unit = b.unit or a.unit or ""
            changes.append(Change(
                case_id=a.case_id,
                display_id="",  # assigned by the pipeline
                concept=concept,
                concept_label=label,
                from_fact_id=a.id,
                to_fact_id=b.id,
                direction="increase" if delta > 0 else "decrease",
                basis=(f"{label} is documented as {a.value_num:g} {unit} on "
                       f"{a.obs_date} and {b.value_num:g} {unit} on {b.obs_date} "
                       f"in the uploaded records.").replace("  ", " "),
                unit=unit or None,
                from_date=a.obs_date,
                to_date=b.obs_date,
                from_value=a.value_num,
                to_value=b.value_num,
                delta=delta,
            ))
            rels.append(Relationship(
                case_id=a.case_id, rel_type=RelType.CHANGED_TO,
                from_type="fact", from_id=a.id, to_type="fact", to_id=b.id,
                detail=(f"Documented change in {label}: {a.value_num:g} on "
                        f"{a.obs_date} to {b.value_num:g} on {b.obs_date}."),
                status=Status.CHANGED,
            ))
            rels.append(Relationship(
                case_id=b.case_id, rel_type=RelType.CHANGED_FROM,
                from_type="fact", from_id=b.id, to_type="fact", to_id=a.id,
                detail=(f"Preceding documented {label}: {a.value_num:g} on "
                        f"{a.obs_date}."),
                status=Status.CHANGED,
            ))
    changes.sort(key=lambda c: (c.concept, c.from_date or "", c.to_date or ""))
    return changes, rels


def detect_series(facts: list[Fact]) -> dict[str, dict]:
    """Per-concept ordered series for charting. One point per observation date."""
    out: dict[str, dict] = {}
    for concept, group in group_by_concept(facts).items():
        by_date = _representatives(group)
        if len(by_date) < 2:
            continue
        pts = [{"date": dt, "value": by_date[dt].value_num,
                "unit": by_date[dt].unit, "fact_id": by_date[dt].id,
                "display_id": by_date[dt].display_id}
               for dt in sorted(by_date)]
        out[concept] = {
            "concept": concept,
            "label": LX.concept_label(concept),
            "unit": next((p["unit"] for p in pts if p["unit"]), None),
            "points": pts,
        }
    return out
