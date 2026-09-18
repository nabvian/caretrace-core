"""Medical Pack — the composed vocabulary the core engine is configured with.

This module used to *be* the laboratory vocabulary. It is now the composed view
over every enabled pack (laboratory, imaging, cardiology, neurophysiology,
molecular), re-exported under the names the engine already reads so that adding
a modality never touches engine code.

The vocabulary itself lives in `caretrace/packs/<modality>/pack.py`; the
composition rules live in `caretrace/packs/registry.py`.
"""
from __future__ import annotations

from ..base import (ClaimTypeDef, ConceptDef, Pack,  # noqa: F401
                    StatusConceptDef, StatusValue)
from ..registry import (  # noqa: F401
    AMBIGUOUS_SYNONYMS,
    ANCHORED_PHRASES,
    CLAIM_LOOKBACK_DAYS,
    CLAIM_TYPE_INDEX,
    CLAIM_TYPES,
    CONCEPT_MODALITY,
    CONCEPTS,
    CONFLICT_WINDOW_DAYS,
    DEFAULT_CLAIM_LOOKBACK_DAYS,
    DEFAULT_CONFLICT_WINDOW_DAYS,
    DOCUMENT_CUES,
    DOCUMENT_REFERENCE_PATTERNS,
    FILENAME_CUES,
    FOLLOWUP_EXPECTATIONS,
    FOLLOWUP_PATTERNS,
    MEDICATION_CLASS_TERMS,
    MEDICATION_SYNONYMS,
    PACKS,
    PACKS_BY_KEY,
    STATUS_CONCEPTS,
    STATUS_MODALITY,
    STATUS_PHRASES,
    STATUS_VALUE_INDEX,
    SYNONYM_INDEX,
    UNIT_ALIAS_INDEX,
    UNSUPPORTED_CONCEPT_LABELS,
    claim_label,
    claim_lookback_days,
    concept_label,
    conflict_window_days,
    modality_of,
    pack_summary,
    status_value_label,
    status_value_positive,
)

__all__ = [
    "AMBIGUOUS_SYNONYMS", "ANCHORED_PHRASES", "CLAIM_LOOKBACK_DAYS", "CLAIM_TYPE_INDEX",
    "CLAIM_TYPES", "CONCEPT_MODALITY", "CONCEPTS", "CONFLICT_WINDOW_DAYS", "DOCUMENT_CUES", "FILENAME_CUES",
    "ClaimTypeDef", "ConceptDef", "DEFAULT_CLAIM_LOOKBACK_DAYS",
    "DEFAULT_CONFLICT_WINDOW_DAYS", "DOCUMENT_REFERENCE_PATTERNS",
    "FOLLOWUP_EXPECTATIONS", "FOLLOWUP_PATTERNS", "MEDICATION_CLASS_TERMS",
    "MEDICATION_SYNONYMS", "PACKS", "PACKS_BY_KEY", "Pack", "STATUS_CONCEPTS",
    "STATUS_MODALITY", "STATUS_PHRASES", "STATUS_VALUE_INDEX",
    "StatusConceptDef", "StatusValue", "status_value_label",
    "status_value_positive", "SYNONYM_INDEX", "UNIT_ALIAS_INDEX",
    "UNSUPPORTED_CONCEPT_LABELS", "claim_label", "claim_lookback_days",
    "concept_label", "conflict_window_days", "modality_of", "pack_summary",
]
