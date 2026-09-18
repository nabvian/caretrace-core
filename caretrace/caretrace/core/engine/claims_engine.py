"""Claim evidence resolution.

For each claim, look for observations in the record that the Medical Pack
declares relevant to that claim type, and classify each as supporting or
contradicting using the pack's declared thresholds.

Three outcomes, and only three:
    SUPPORTED             at least one supporting observation located
    CONTRADICTED          at least one contradicting observation located
    NO_LOCATED_EVIDENCE   the required evidence is not in the uploaded records

NO_LOCATED_EVIDENCE never means the claim is false. It means CARETRACE could
not locate evidence for it in what was uploaded. When both supporting and
contradicting evidence exist, the claim is marked CONTRADICTED and both sides
are retained — the engine does not adjudicate.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from ..models import (Claim, ClaimEvidenceStatus, Fact, Relationship, RelType,
                      Status)
from ...packs.medical import lexicon as LX


def _d(iso: Optional[str]) -> Optional[date]:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None


def _dedupe(items: list[str]) -> list[str]:
    """Order-preserving de-duplication."""
    seen: set[str] = set()
    return [x for x in items if not (x in seen or seen.add(x))]


def _direction_matches(op: str, value: float, threshold: float) -> bool:
    """Evaluate a pack-declared direction rule. Unknown operators never match."""
    if op == "lt":
        return value < threshold
    if op == "lte":
        return value <= threshold
    if op == "gt":
        return value > threshold
    if op == "gte":
        return value >= threshold
    return False


_OPPOSITE = {"lt": "gte", "lte": "gt", "gt": "lte", "gte": "lt"}


def resolve_claims(claims: list[Claim], facts: list[Fact]
                   ) -> tuple[list[dict], list[Relationship]]:
    """Resolve every claim against the observations in the record.

    Outcomes are strictly about what could be LOCATED:
      SUPPORTING_EVIDENCE     a qualifying observation was found
      CONTRADICTING_EVIDENCE  an observation pointing the other way was found
      NO_LOCATED_EVIDENCE     the required evidence is not in the records

    NO_LOCATED_EVIDENCE is never a statement that the claim is false, and the
    engine never adjudicates when both kinds of evidence exist — both are kept
    and the claim is flagged as having contradicting evidence.
    """
    results: list[dict] = []
    rels: list[Relationship] = []

    facts_by_concept: dict[str, list[Fact]] = {}
    status_by_concept: dict[str, list[Fact]] = {}
    for f in facts:
        if f.value_num is not None:
            facts_by_concept.setdefault(f.concept, []).append(f)
        elif f.value_key:
            status_by_concept.setdefault(f.concept, []).append(f)

    for claim in claims:
        ctd = LX.CLAIM_TYPE_INDEX.get(claim.claim_type)
        if ctd is None:
            results.append({
                "claim": claim,
                "status": ClaimEvidenceStatus.NOT_ASSESSED,
                "supporting": [], "contradicting": [],
                "required_concepts": [], "required_labels": [],
                "located_concepts": [], "missing_concepts": [],
                "missing_labels": [],
                "lookback_days": 0,
                "note": ("No evidence requirements are declared for this claim "
                         "type in the active pack; CARETRACE did not assess it."),
            })
            continue

        lookback = LX.claim_lookback_days(claim.claim_type)
        claim_date = _d(claim.claim_date)
        directions = {c: (op, thr) for c, op, thr in ctd.supportive_direction}

        supporting: list[tuple[Fact, str]] = []
        contradicting: list[tuple[Fact, str]] = []
        located: set[str] = set()
        # A required test that EXISTS in the records but falls outside the claim's
        # window. Recorded separately so the gap can say "present but dated after
        # the claim" instead of a bare "not located", which a reviewer who has
        # seen the test elsewhere would read as an extraction miss.
        out_of_window: list[tuple[Fact, str, str]] = []

        # Qualitative evidence. A radiology or ECG report states most of its
        # result as text, so a claim of normality is evidenced by documented
        # absences and contradicted by a documented positive finding. Which
        # direction supports the claim is declared by the pack, never inferred
        # from the claim's wording.
        if ctd.supportive_status_polarity is not None:
            want = ctd.supportive_status_polarity
            for concept in ctd.requires_any:
                for f in status_by_concept.get(concept, []):
                    fd = _d(f.obs_date)
                    if claim_date and fd:
                        if fd > claim_date:
                            out_of_window.append((f, concept, "after_claim"))
                            continue
                        if (claim_date - fd).days > lookback:
                            out_of_window.append((f, concept, "before_lookback"))
                            continue
                    located.add(concept)
                    positive = LX.status_value_positive(concept, f.value_key)
                    if positive is None:
                        continue        # pack declares no polarity for this class
                    if positive == want:
                        supporting.append((f, concept))
                    else:
                        contradicting.append((f, concept))

        for concept in ctd.requires_any:
            for f in facts_by_concept.get(concept, []):
                fd = _d(f.obs_date)
                # Evidence dated after the claim cannot retrospectively support
                # it, and evidence older than the pack's lookback is not treated
                # as evidence for this claim.
                if claim_date and fd:
                    if fd > claim_date:
                        out_of_window.append((f, concept, "after_claim"))
                        continue
                    if (claim_date - fd).days > lookback:
                        out_of_window.append((f, concept, "before_lookback"))
                        continue
                located.add(concept)
                rule = directions.get(concept)
                if rule is None:
                    continue
                op, thr = rule
                if _direction_matches(op, f.value_num, thr):
                    supporting.append((f, concept))
                elif _direction_matches(_OPPOSITE.get(op, ""), f.value_num, thr):
                    contradicting.append((f, concept))

        required = list(ctd.requires_any)
        missing = [c for c in required if c not in located]
        # Two concept keys can share a display label (aliases). A reviewer should
        # see one row per test that is absent, not one per key.
        missing_labels = _dedupe([LX.concept_label(c) for c in missing]) \
            or _dedupe(list(ctd.requires_labels))

        if contradicting:
            status = ClaimEvidenceStatus.CONTRADICTING_EVIDENCE
        elif supporting:
            status = ClaimEvidenceStatus.SUPPORTING_EVIDENCE
        else:
            status = ClaimEvidenceStatus.NO_LOCATED_EVIDENCE

        def _detail(f: Fact, concept: str) -> str:
            if f.value_num is None:
                return (f"{f.value_text or f.value_key} documented "
                        f"{f.obs_date}.")
            return (f"{LX.concept_label(concept)} {f.value_num:g} "
                    f"{f.unit or ''} documented {f.obs_date}.").replace("  ", " ")

        for f, concept in supporting:
            rels.append(Relationship(
                case_id=claim.case_id, rel_type=RelType.SUPPORTS,
                from_type="fact", from_id=f.id,
                to_type="claim", to_id=claim.id,
                detail=_detail(f, concept), status=Status.DOCUMENTED,
            ))
        for f, concept in contradicting:
            rels.append(Relationship(
                case_id=claim.case_id, rel_type=RelType.CONTRADICTS,
                from_type="fact", from_id=f.id,
                to_type="claim", to_id=claim.id,
                detail=_detail(f, concept), status=Status.UNRESOLVED,
            ))
        if status == ClaimEvidenceStatus.NO_LOCATED_EVIDENCE:
            rels.append(Relationship(
                case_id=claim.case_id, rel_type=RelType.MISSING_SUPPORT,
                from_type="claim", from_id=claim.id,
                to_type="concept", to_id=",".join(missing) or claim.claim_type,
                detail=("Evidence declared as required for this claim type was "
                        "not located in the uploaded records: "
                        + ", ".join(missing_labels)),
                status=Status.MISSING,
            ))

        results.append({
            "claim": claim,
            "status": status,
            "supporting": supporting,
            "contradicting": contradicting,
            "required_concepts": required,
            "required_labels": list(ctd.requires_labels),
            "located_concepts": sorted(located),
            "missing_concepts": missing,
            "missing_labels": missing_labels,
            "lookback_days": lookback,
            "out_of_window": [
                {"fact_id": f.id, "concept": c,
                 "label": LX.concept_label(c),
                 "value": f.value_num, "unit": f.unit, "obs_date": f.obs_date,
                 "value_text": f.value_text,
                 "reason": why,
                 "explanation": (
                     f"{LX.concept_label(c)} is documented in the records "
                     + (f"({f.value_text or f.value_key} on {f.obs_date}) "
                        if f.value_num is None else
                        f"({f.value_num:g} {f.unit or ''} on {f.obs_date}) ")
                     + "but is dated "
                     + ("after this claim, so it cannot be evidence the claim was "
                        "based on." if why == "after_claim" else
                        f"more than {lookback} days before this claim."))
                 .replace("  ", " ")}
                for f, c, why in out_of_window],
            "note": (f"Evidence searched: {', '.join(ctd.requires_labels)}. "
                     f"Lookback window: {lookback} days before the claim date."),
        })
    return results, rels
