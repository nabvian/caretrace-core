"""Pack contract — what a domain vocabulary must supply to configure the engine.

A pack is *data*. The engine reads a pack; it never imports one directly. Adding
a modality (imaging, cardiology, neurophysiology, molecular) means adding a pack
module and registering it, not editing the engine.

The types here are re-exported from the laboratory pack for backwards
compatibility, so existing imports keep working while packs multiply.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConceptDef:
    """A measurable concept: what it is called, its unit, and what counts as a
    material difference between two documented values of it."""
    key: str
    label: str
    canonical_unit: str
    # Absolute difference at/above which two same-episode values are treated as
    # materially different. Chosen to sit above ordinary inter-assay noise.
    material_abs: float
    # Alternative: relative difference threshold (fraction).
    material_rel: float
    synonyms: tuple[str, ...]
    unit_aliases: tuple[tuple[str, str], ...] = ()
    # Which modality this concept belongs to, for UI grouping and reporting.
    modality: str = "LABORATORY"


@dataclass(frozen=True)
class ClaimTypeDef:
    key: str
    label: str
    patterns: tuple[str, ...]
    requires_any: tuple[str, ...]
    requires_labels: tuple[str, ...]
    # concept -> (comparator, threshold) where comparator in {"lt","gt"}
    supportive_direction: tuple[tuple[str, str, float], ...] = ()
    # For claims whose evidence is a qualitative finding rather than a number:
    # whether the claim is supported by a finding being PRESENT (True) or by
    # its ABSENCE (False). 'Imaging reported normal' is supported by absences
    # and contradicted by a positive finding; 'infarct confirmed' is the
    # reverse. Declared here so the engine never has to infer intent from
    # wording. None means this claim type takes no status evidence.
    supportive_status_polarity: bool | None = None
    modality: str = "LABORATORY"


@dataclass(frozen=True)
class StatusValue:
    """One mutually-exclusive value a qualitative finding can take.

    Grouping phrases into value classes is what makes status conflict detection
    exact rather than string-based: 'no acute infarct' and 'no infarct' are the
    same documented finding, while 'acute infarct' is a different one. Two
    documents reporting different value keys for the same concept in the same
    episode disagree; two reporting different phrases of the same key do not.
    """
    key: str
    label: str
    phrases: tuple[str, ...]
    # Whether this value asserts the finding is present. Reported in the UI so
    # a reviewer sees the polarity of each side without reading the phrase.
    positive: bool = True


@dataclass(frozen=True)
class StatusConceptDef:
    key: str
    label: str
    values: tuple[StatusValue, ...]
    modality: str = "OTHER"


@dataclass(frozen=True)
class Pack:
    """One domain vocabulary. Packs compose; none of them is privileged."""
    key: str
    label: str
    modality: str
    concepts: dict[str, ConceptDef] = field(default_factory=dict)
    claim_types: tuple[ClaimTypeDef, ...] = ()
    medication_synonyms: dict[str, str] = field(default_factory=dict)
    medication_class_terms: dict[str, tuple[str, ...]] = field(default_factory=dict)
    unsupported_concept_labels: dict[str, str] = field(default_factory=dict)
    followup_patterns: tuple[tuple[str, str], ...] = ()
    document_reference_patterns: tuple[tuple[str, str, str], ...] = ()
    conflict_window_days: dict[str, int] = field(default_factory=dict)
    claim_lookback_days: dict[str, int] = field(default_factory=dict)
    followup_expectations: dict[str, tuple[int, str | None]] = field(default_factory=dict)
    # Qualitative findings this modality reports as text rather than numbers
    # ('no acute infarct', 'sinus rhythm'). Each concept declares its mutually
    # exclusive value classes so the conflict engine can compare two documented
    # statuses of the same concept exactly.
    status_concepts: dict[str, StatusConceptDef] = field(default_factory=dict)
    # Status phrases so generic that they only mean something next to a label
    # ('Detected', 'Negative'). They are recognised only when they follow a
    # label separator, so they cannot be picked up from inside a longer
    # sentence about a different finding.
    anchored_phrases: tuple[str, ...] = ()
    # Phrases that identify a document as being of a given kind, as
    # (doc_type, (phrase, ...)). A modality knows the headings its own reports
    # print, so classification is declared here rather than hard-coded in the
    # extractor -- otherwise adding a modality means editing core.
    document_cues: tuple[tuple[str, tuple[str, ...]], ...] = ()
    # Weak filename hints for the same kinds. Never decisive on their own.
    filename_cues: tuple[tuple[str, tuple[str, ...]], ...] = ()
