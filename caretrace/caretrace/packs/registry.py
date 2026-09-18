"""Pack registry — composes the enabled domain packs into one vocabulary.

The engine reads a single flat vocabulary. This module is what turns N packs
into that one view, and it is the only place where pack precedence is decided.

Composition rules, stated once here so they are inspectable:

* Concept keys are namespaced by nothing -- they are globally unique across
  packs by construction. A collision is a packaging error, so it raises rather
  than silently letting one pack shadow another.
* A synonym claimed by two packs is ambiguous. Rather than pick a winner by
  import order, the ambiguous surface form is dropped from the synonym index and
  recorded in AMBIGUOUS_SYNONYMS. An ambiguous label then resolves to
  UNRECOGNISED and is *retained* as an unmapped measurement, which is the
  honest outcome: CARETRACE saw a value it cannot confidently name.
* Windows and lookbacks are per-concept/per-claim, so they merge without
  conflict.
"""
from __future__ import annotations

import collections
from typing import Iterable

from .base import ClaimTypeDef, ConceptDef, Pack, StatusConceptDef, StatusValue


class PackCollision(RuntimeError):
    """Two packs defined the same concept or claim key."""


def _load_packs() -> tuple[Pack, ...]:
    from .cardiology.pack import PACK as CARDIOLOGY
    from .imaging.pack import PACK as IMAGING
    from .laboratory.pack import PACK as LABORATORY
    from .molecular.pack import PACK as MOLECULAR
    from .neurophysiology.pack import PACK as NEUROPHYSIOLOGY
    return (LABORATORY, IMAGING, CARDIOLOGY, NEUROPHYSIOLOGY, MOLECULAR)


PACKS: tuple[Pack, ...] = _load_packs()
PACKS_BY_KEY: dict[str, Pack] = {p.key: p for p in PACKS}


def _merge_unique(packs: Iterable[Pack], attr: str, keyfn) -> dict:
    out: dict = {}
    owner: dict = {}
    for p in packs:
        for item in getattr(p, attr).values() if isinstance(getattr(p, attr), dict) \
                else getattr(p, attr):
            k = keyfn(item)
            if k in out:
                raise PackCollision(
                    f"{attr} key {k!r} defined by both {owner[k]!r} and {p.key!r}")
            out[k], owner[k] = item, p.key
    return out


# --- concepts ---------------------------------------------------------------
CONCEPTS: dict[str, ConceptDef] = _merge_unique(PACKS, "concepts", lambda c: c.key)
CONCEPT_MODALITY: dict[str, str] = {k: c.modality for k, c in CONCEPTS.items()}

# --- claim types ------------------------------------------------------------
_claims: list[ClaimTypeDef] = []
for _p in PACKS:
    _claims.extend(_p.claim_types)
_seen: set[str] = set()
for _c in _claims:
    if _c.key in _seen:
        raise PackCollision(f"claim key {_c.key!r} defined twice")
    _seen.add(_c.key)
CLAIM_TYPES: tuple[ClaimTypeDef, ...] = tuple(_claims)
CLAIM_TYPE_INDEX: dict[str, ClaimTypeDef] = {c.key: c for c in CLAIM_TYPES}

# --- synonym index, with ambiguity made explicit ---------------------------
_claimed: dict[str, set[str]] = collections.defaultdict(set)
for _key, _cd in CONCEPTS.items():
    for _syn in _cd.synonyms:
        _claimed[_syn.strip().lower()].add(_key)

AMBIGUOUS_SYNONYMS: dict[str, tuple[str, ...]] = {
    s: tuple(sorted(ks)) for s, ks in _claimed.items() if len(ks) > 1}
SYNONYM_INDEX: dict[str, str] = {
    s: next(iter(ks)) for s, ks in _claimed.items() if len(ks) == 1}

UNIT_ALIAS_INDEX: dict[str, dict[str, str]] = {
    k: {a.lower(): c for a, c in cd.unit_aliases} for k, cd in CONCEPTS.items()}

# --- status concepts (qualitative findings) --------------------------------
STATUS_CONCEPTS: dict[str, StatusConceptDef] = {}
STATUS_MODALITY: dict[str, str] = {}
for _p in PACKS:
    for _k, _sc in _p.status_concepts.items():
        if _k in STATUS_CONCEPTS:
            raise PackCollision(f"status concept {_k!r} defined twice")
        STATUS_CONCEPTS[_k] = _sc
        STATUS_MODALITY[_k] = _sc.modality or _p.modality

# (phrase_lower, concept_key, value_key, phrase_as_written), longest phrase
# first so 'no epileptiform activity' is matched before 'epileptiform activity'.
STATUS_PHRASES: tuple[tuple[str, str, str, str], ...] = tuple(sorted(
    ((ph.lower(), ck, sv.key, ph)
     for ck, sc in STATUS_CONCEPTS.items() for sv in sc.values for ph in sv.phrases),
    key=lambda t: -len(t[0])))

STATUS_VALUE_INDEX: dict[tuple[str, str], StatusValue] = {
    (ck, sv.key): sv for ck, sc in STATUS_CONCEPTS.items() for sv in sc.values}


def status_value_label(concept: str, value_key: str) -> str:
    sv = STATUS_VALUE_INDEX.get((concept, value_key))
    return sv.label if sv else value_key.replace("_", " ").capitalize()


def status_value_positive(concept: str, value_key: str) -> bool | None:
    sv = STATUS_VALUE_INDEX.get((concept, value_key))
    return None if sv is None else sv.positive


ANCHORED_PHRASES: frozenset[str] = frozenset(
    ph.lower() for p in PACKS for ph in p.anchored_phrases)

# --- flat merges ----------------------------------------------------------
MEDICATION_SYNONYMS: dict[str, str] = {}
MEDICATION_CLASS_TERMS: dict[str, tuple[str, ...]] = {}
UNSUPPORTED_CONCEPT_LABELS: dict[str, str] = {}
CONFLICT_WINDOW_DAYS: dict[str, int] = {}
CLAIM_LOOKBACK_DAYS: dict[str, int] = {}
FOLLOWUP_EXPECTATIONS: dict[str, tuple[int, str | None]] = {}
_followup: list[tuple[str, str]] = []
_docrefs: list[tuple[str, str, str]] = []
for _p in PACKS:
    MEDICATION_SYNONYMS.update(_p.medication_synonyms)
    MEDICATION_CLASS_TERMS.update(_p.medication_class_terms)
    UNSUPPORTED_CONCEPT_LABELS.update(_p.unsupported_concept_labels)
    CONFLICT_WINDOW_DAYS.update(_p.conflict_window_days)
    CLAIM_LOOKBACK_DAYS.update(_p.claim_lookback_days)
    FOLLOWUP_EXPECTATIONS.update(_p.followup_expectations)
    _followup.extend(_p.followup_patterns)
    _docrefs.extend(_p.document_reference_patterns)
FOLLOWUP_PATTERNS: tuple[tuple[str, str], ...] = tuple(_followup)
DOCUMENT_REFERENCE_PATTERNS: tuple[tuple[str, str, str], ...] = tuple(_docrefs)

DEFAULT_CONFLICT_WINDOW_DAYS: int = 2
DEFAULT_CLAIM_LOOKBACK_DAYS: int = 180


def conflict_window_days(concept: str) -> int:
    return CONFLICT_WINDOW_DAYS.get(concept, DEFAULT_CONFLICT_WINDOW_DAYS)


def claim_lookback_days(claim_type: str) -> int:
    return CLAIM_LOOKBACK_DAYS.get(claim_type, DEFAULT_CLAIM_LOOKBACK_DAYS)


def claim_label(key: str) -> str:
    cd = CLAIM_TYPE_INDEX.get(key)
    return cd.label if cd else key.replace("_", " ").title()


def concept_label(key: str) -> str:
    cd = CONCEPTS.get(key)
    if cd:
        return cd.label
    lbl = UNSUPPORTED_CONCEPT_LABELS.get(key)
    if lbl:
        return lbl
    sc = STATUS_CONCEPTS.get(key)
    if sc:
        return sc.label
    return key.replace("_", " ").title()


def modality_of(concept: str) -> str:
    return CONCEPT_MODALITY.get(concept) or STATUS_MODALITY.get(concept, "OTHER")


def pack_summary() -> list[dict]:
    """What the admin screen reports: which packs are active and what each adds."""
    return [{
        "key": p.key, "label": p.label, "modality": p.modality,
        "concepts": len(p.concepts),
        "status_concepts": len(p.status_concepts),
        "status_values": sum(len(sc.values) for sc in p.status_concepts.values()),
        "anchored_phrases": len(p.anchored_phrases),
        "claim_types": len(p.claim_types),
        "document_reference_patterns": len(p.document_reference_patterns),
    } for p in PACKS]


# --------------------------------------------------------------------------
# Teach the unit grammar the spellings these packs' instruments print.
# Done at import so extraction never has to know which pack owns a spelling.
# --------------------------------------------------------------------------
# Classification cues, merged across packs. Additive rather than unique-keyed:
# several packs may contribute phrases for the same document kind, and a
# document kind may legitimately be claimed by more than one pack.
def _merge_cues(attr: str) -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for pack in PACKS:
        for doc_type, phrases in getattr(pack, attr):
            out.setdefault(doc_type, []).extend(phrases)
    return {k: tuple(dict.fromkeys(v)) for k, v in out.items()}


DOCUMENT_CUES: dict[str, tuple[str, ...]] = _merge_cues("document_cues")
FILENAME_CUES: dict[str, tuple[str, ...]] = _merge_cues("filename_cues")


def _register_unit_aliases() -> int:
    """Register only spellings the UCUM grammar cannot parse at all.

    A concept's unit_aliases serve two different purposes. Some are scale
    conversions the concept needs ('/uL' -> 'x10^9/L' for a white cell count):
    those are meaningful only for that analyte and must stay per-concept, or a
    volume elsewhere in the corpus would be silently rescaled. Others are
    spellings no grammar generates ('bpm', 'beats/min'): those carry no
    analyte-specific assumption and are safe to teach globally, which is what
    lets a rate be recognised on any report that prints it.

    The discriminator is the grammar itself: if it already parses the surface
    form, the alias is a conversion and is left alone.
    """
    from caretrace.core import units as U
    n = 0
    for pack in PACKS:
        for cd in pack.concepts.values():
            for surface, ucum in cd.unit_aliases:
                if U.dimension(surface) is not None:
                    continue        # grammar parses it: a conversion, not a spelling
                U.register_alias(surface, ucum)
                n += 1
    return n


REGISTERED_UNIT_ALIASES = _register_unit_aliases()
