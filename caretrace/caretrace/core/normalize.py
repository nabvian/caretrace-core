"""Deterministic normalization: concepts, units, dates.

Everything here is a pure function. The original surface wording is always
returned alongside the normalized key so provenance survives normalization.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from ..packs.medical import lexicon as LX

# --------------------------------------------------------------------------
# Concept normalization
# --------------------------------------------------------------------------

_SYNONYMS_BY_LENGTH = sorted(LX.SYNONYM_INDEX.items(), key=lambda kv: -len(kv[0]))


def normalize_concept(surface: str) -> Optional[str]:
    """Map a surface label ('Hb', 'PLT', 'Packed Cell Volume') to a concept key."""
    s = re.sub(r"[^a-z0-9 %/\-]", " ", surface.lower())
    s = re.sub(r"\s+", " ", s).strip(" -:")
    if not s:
        return None
    if s in LX.SYNONYM_INDEX:
        return LX.SYNONYM_INDEX[s]
    # tolerate trailing qualifiers, e.g. "hemoglobin (venous)"
    for syn, key in _SYNONYMS_BY_LENGTH:
        if s == syn or s.startswith(syn + " ") or s.endswith(" " + syn):
            return key
    return None


def match_concept(surface: str) -> tuple[Optional[str], str]:
    """Like normalize_concept, but also returns the portion of the surface text
    that actually carried the concept — so a prose fragment such as
    'summary records a haemoglobin' is displayed as 'haemoglobin'."""
    s = re.sub(r"[^a-z0-9 %/\-]", " ", surface.lower())
    s = re.sub(r"\s+", " ", s).strip(" -:")
    if not s:
        return None, surface.strip()
    if s in LX.SYNONYM_INDEX:
        return LX.SYNONYM_INDEX[s], surface.strip()
    for syn, key in _SYNONYMS_BY_LENGTH:
        if s == syn:
            return key, surface.strip()
        if s.startswith(syn + " "):
            return key, surface.strip()[:len(syn)]
        if s.endswith(" " + syn):
            return key, surface.strip()[-len(syn):]
    return None, surface.strip()


# Words that carry no analyte meaning, removed before containment matching so
# a prose fragment reduces to its analyte term.
_STOPWORDS = {
    "the", "a", "an", "of", "was", "is", "were", "are", "with", "and", "on",
    "at", "in", "for", "patient", "patients", "his", "her", "their", "s",
    "shows", "showed", "showing", "noted", "recorded", "reported", "records",
    "summary", "report", "value", "result", "level", "levels", "count",
    "serum", "plasma", "blood", "whole", "venous", "arterial", "capillary",
    "total", "measured", "admission", "discharge", "today", "repeat",
}


_DOTTED_RX = re.compile(r"\b(?:[A-Za-z]\s*\.\s*){2,}[A-Za-z]?\b")


def _undot(surface: str) -> str:
    """'M.C.V.' -> 'MCV'. Dotted abbreviations are a spelling convention, not a
    different concept, and they appear in reports from any institution."""
    def _join(m):
        return re.sub(r"[.\s]", "", m.group(0)) + " "
    return re.sub(r"\s{2,}", " ", _DOTTED_RX.sub(_join, surface or "")).strip()


def resolve_label(surface: str) -> tuple[Optional[str], str, str]:
    """Resolve any surface label to (concept_key, display_label, method).

    Layout-agnostic extraction produces labels of wildly varying cleanliness:
    a tidy table cell ('Haemoglobin'), an abbreviation ('M.C.V.'), or a prose
    fragment ("The patient's haemoglobin was"). All three must reach the same
    concept, and a label the vocabulary does not know must NOT be discarded.

    `method` is one of EXACT | EDGE | CONTAINED | UNRECOGNISED and is carried
    through to the fact so the operator can see how the mapping was made.
    """
    key = normalize_concept(surface)
    if key:
        return key, LX.concept_label(key), "EXACT"

    undotted = _undot(surface)
    if undotted != surface:
        key = normalize_concept(undotted)
        if key:
            return key, LX.concept_label(key), "EXACT"

    s = re.sub(r"[^a-z0-9 %/\-]", " ", undotted.lower())
    words = [w for w in re.split(r"\s+", s) if w and w not in _STOPWORDS]
    if not words:
        return None, (surface or "").strip(), "UNRECOGNISED"

    # Longest synonym contained in the reduced word sequence wins. Longest-first
    # so 'mean corpuscular volume' beats 'volume'.
    reduced = " ".join(words)
    for syn, k in _SYNONYMS_BY_LENGTH:
        if syn == reduced or re.search(rf"(?<![a-z0-9]){re.escape(syn)}(?![a-z0-9])", reduced):
            return k, LX.concept_label(k), "CONTAINED"

    # Not in the vocabulary. Keep the measurement under a stable slug so it is
    # still counted, still traceable, and still comparable with itself over
    # time -- just not asserted to be a known clinical concept.
    slug = re.sub(r"[^a-z0-9]+", "_", " ".join(words)).strip("_")[:48]
    display = re.sub(r"\s+", " ", (surface or "").strip()) or slug
    return (f"unmapped:{slug}" if slug else None), display, "UNRECOGNISED"


def is_unmapped(concept: Optional[str]) -> bool:
    """Whether a concept key came from an analyte outside the vocabulary."""
    return bool(concept and concept.startswith("unmapped:"))


def normalize_unit(concept: str, unit: Optional[str]) -> Optional[str]:
    if not unit:
        cd = LX.CONCEPTS.get(concept)
        return cd.canonical_unit if cd else None
    u = unit.strip()
    alias = LX.UNIT_ALIAS_INDEX.get(concept, {}).get(u.lower())
    if alias:
        return alias
    cd = LX.CONCEPTS.get(concept)
    if cd and u.lower() == cd.canonical_unit.lower():
        return cd.canonical_unit
    return u


def normalize_drug(name: str) -> str:
    n = re.sub(r"\s+", " ", name.strip().lower())
    n = re.sub(r"[.,;:]+$", "", n)
    return LX.MEDICATION_SYNONYMS.get(n, n)


# --------------------------------------------------------------------------
# Date normalization
# --------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

_DATE_PATTERNS = [
    # 18 January 2026 / 18 Jan 2026
    (re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b"), "dmy", "day"),
    # January 18, 2026
    (re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b"), "mdy", "day"),
    # 2026-01-18
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso", "day"),
    # 18/01/2026 (day-first; the corpus uses no ambiguous US-style dates)
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), "dmy_num", "day"),
    # January 2026  (month precision)
    (re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{4})\b"), "my", "month"),
]


def parse_date(text: str) -> tuple[Optional[str], str]:
    """Return (ISO date or None, precision)."""
    for rx, kind, precision in _DATE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        try:
            if kind == "dmy":
                d, mon, y = int(m.group(1)), _MONTHS.get(m.group(2)[:3].lower()), int(m.group(3))
                if not mon:
                    continue
                return date(y, mon, d).isoformat(), precision
            if kind == "mdy":
                mon, d, y = _MONTHS.get(m.group(1)[:3].lower()), int(m.group(2)), int(m.group(3))
                if not mon:
                    continue
                return date(y, mon, d).isoformat(), precision
            if kind == "iso":
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat(), precision
            if kind == "dmy_num":
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat(), precision
            if kind == "my":
                mon = _MONTHS.get(m.group(1)[:3].lower())
                if not mon:
                    continue
                return date(int(m.group(2)), mon, 1).isoformat(), "month"
        except ValueError:
            continue
    return None, "unknown"


_DATE_LABEL_RX = re.compile(
    r"(?:report date|reported on|date of report|consultation date|follow-?up date|"
    r"list date|discharge date|admission date|compiled|sample date|date)\s*[:\-]\s*"
    r"([^\n]{4,40})", re.I)


def find_document_date(text: str) -> tuple[Optional[str], str, bool]:
    """Find a document/page date.

    Returns (iso, precision, labelled). `labelled` is True only when the date
    came from an explicit label such as 'Report Date:' — an unlabelled fallback
    is just the first date appearing in the text and must not be allowed to
    override a real document date (a date mentioned in passing is not the date
    of the page).
    """
    best: Optional[tuple[str, str]] = None
    for m in _DATE_LABEL_RX.finditer(text):
        iso, prec = parse_date(m.group(1))
        if iso:
            label = m.group(0).lower()
            # 'discharge date' wins over 'admission date' on a discharge summary
            if best is None or "discharge date" in label or "report date" in label:
                best = (iso, prec)
    if best:
        return best[0], best[1], True
    iso, prec = parse_date(text)
    return iso, prec, False


def material_difference(concept: str, a: float, b: float) -> bool:
    """Deterministic materiality test used by the conflict engine."""
    cd = LX.CONCEPTS.get(concept)
    diff = abs(a - b)
    if cd is None:
        return diff > 0
    base = max(abs(a), abs(b), 1e-9)
    return diff >= cd.material_abs or (diff / base) >= cd.material_rel


def confidence_band(value: float) -> str:
    if value >= 0.90:
        return "High"
    if value >= 0.75:
        return "Moderate"
    return "Low"
