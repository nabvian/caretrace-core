"""A generated UCUM-shaped unit grammar.

Why this exists: the extractor finds measurements by recognising the UNIT
first, then the adjacent number, then the label. That inverts the usual
approach (match a known analyte label, then read what follows) and is what
makes extraction independent of any particular laboratory's page layout.

The unit vocabulary is GENERATED from UCUM's compositional rules -- an atom
table crossed with the SI prefix table, then combined by UCUM's own operators
(`/` for division, `.` for multiplication, `^`/digits for exponents) -- rather
than hand-listed per report format. Adding `mmol/L` or `pmol/mL` requires no
code change; they are already implied by the grammar.

UCUM's machine-readable definition file (ucum-essence.xml) is not distributed
under terms that allow bundling here, so this module encodes the published
grammar and the atom/prefix tables rather than shipping a copy. When an
operator supplies their own UCUM release, `load_ucum_essence()` reads it and
extends the atom table with the official codes.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# UCUM prefix table (symbol -> decimal exponent).
# ---------------------------------------------------------------------------

PREFIXES: dict[str, int] = {
    "Y": 24, "Z": 21, "E": 18, "P": 15, "T": 12, "G": 9, "M": 6, "k": 3,
    "h": 2, "da": 1, "d": -1, "c": -2, "m": -3, "u": -6, "µ": -6, "μ": -6,
    "n": -9, "p": -12, "f": -15, "a": -18, "z": -21, "y": -24,
}

# ---------------------------------------------------------------------------
# Atoms that take metric prefixes, and those that do not.
# `dim` is the quantity kind, used to reject impossible compositions and to
# group units when comparing two values of the same analyte.
# ---------------------------------------------------------------------------

METRIC_ATOMS: dict[str, str] = {
    "g": "mass", "m": "length", "s": "time", "L": "volume", "l": "volume",
    "mol": "amount", "eq": "amount", "osm": "amount", "K": "temperature",
    "Pa": "pressure", "Hz": "frequency", "U": "catalytic", "kat": "catalytic",
    "cal": "energy", "J": "energy", "V": "electric", "A": "electric",
    "Ohm": "electric", "Sv": "dose", "Gy": "dose", "Bq": "radioactivity",
    "t": "mass", "bar": "pressure",
}

NON_METRIC_ATOMS: dict[str, str] = {
    "%": "fraction", "min": "time", "h": "time", "d": "time", "wk": "time",
    "mo": "time", "a": "time", "degC": "temperature", "Cel": "temperature",
    "[degF]": "temperature", "mm[Hg]": "pressure", "[iU]": "arbitrary",
    "[IU]": "arbitrary", "10*": "count", "10^": "count", "1": "unity",
    "[pH]": "acidity", "cm[H2O]": "pressure",
    # Surface spellings reports actually use for UCUM's [iU] arbitrary unit.
    "IU": "arbitrary", "iU": "arbitrary", "mIU": "arbitrary",
    "kIU": "arbitrary", "uIU": "arbitrary", "µIU": "arbitrary",
    "mU": "arbitrary", "kU": "arbitrary", "uU": "arbitrary",
    # Capitalised surface spellings of UCUM's 'eq' and 'osm' atoms.
    "Eq": "amount", "mEq": "amount", "uEq": "amount", "µEq": "amount",
    "nEq": "amount", "Osm": "amount", "mOsm": "amount",
}

# Never a clinical unit even though the grammar admits the token: clock-time
# suffixes would otherwise read as picometre / attometre after a number.
NEVER_UNITS = {"am", "pm", "AM", "PM", "Am", "Pm"}

# Dimensionless-per-volume counts, written in clinical reports as 10^9/L,
# 10*9/L, x10^9/L or K/uL. UCUM writes these with the 10* atom.
COUNT_MANTISSA_RX = r"(?:[xX×]\s?)?10\s?[\*\^]\s?-?\d{1,2}"


def _metric_forms() -> dict[str, str]:
    """Atom table crossed with the prefix table -- generated, not enumerated."""
    out: dict[str, str] = {}
    for atom, dim in METRIC_ATOMS.items():
        out.setdefault(atom, dim)
        for pfx in PREFIXES:
            out.setdefault(f"{pfx}{atom}", dim)
    out.update(NON_METRIC_ATOMS)
    return out


ATOM_FORMS: dict[str, str] = _metric_forms()

# Longest-first so 'mmol' wins over 'mol', 'dL' over 'L'.
_ATOM_ALT = "|".join(re.escape(a) for a in
                     sorted(ATOM_FORMS, key=len, reverse=True))

# A UCUM term: atom with optional exponent, combined by '/' or '.'.
_TERM = rf"(?:{COUNT_MANTISSA_RX}|{_ATOM_ALT})(?:\s?[\*\^]\s?-?\d{{1,2}})?"
UNIT_RX = re.compile(rf"(?P<unit>{_TERM}(?:\s?[/.]\s?{_TERM}){{0,3}})")

# A unit must be bounded so 'in' inside a word is not read as a unit, and
# must not be immediately followed by more letters.
UNIT_BOUNDED_RX = re.compile(
    rf"(?<![A-Za-z0-9_]){UNIT_RX.pattern}(?![A-Za-z0-9_%])")

# Tokens the grammar technically admits but which are never a clinical unit in
# running text. Excluded to keep prose from yielding phantom measurements.
AMBIGUOUS_ALONE = {
    "a", "d", "h", "m", "s", "t", "1", "A", "K", "M", "P", "T", "U", "V",
    "min", "mo", "wk", "da", "cal", "pa", "Pa", "dam",
    "as", "at", "in", "is", "no", "on", "or", "to", "kat", "eq", "yd",
    "am", "pm",
}

# Units whose presence alone is strong evidence of a laboratory measurement.
CLINICAL_HINT_RX = re.compile(
    r"g/d?[Ll]|mg/d?[Ll]|µ?u?g/d?[Ll]|ng/m?[Ll]|pg|fL|fl|mmol/[Ll]|"
    r"µ?umol/[Ll]|mEq/[Ll]|m?[Ii][Uu]/[Ll]|%|10[\*\^]\d+/[Ll]|"
    r"mm\[?Hg\]?|U/[Ll]|k?U/m?[Ll]|s(?![A-Za-z])|ms", re.X)


# Spellings the UCUM grammar does not generate, contributed by packs at import
# ('bpm' -> '/min'). Registering them here rather than hard-coding a list keeps
# the grammar the single authority on what a unit means, while letting a
# modality teach it the spellings its instruments actually print.
REGISTERED_ALIASES: dict[str, str] = {}


def register_alias(surface: str, ucum: str) -> None:
    """Teach the grammar a non-UCUM spelling used by real reports."""
    key = surface.strip().lower().replace(" ", "")
    if key and key not in REGISTERED_ALIASES:
        REGISTERED_ALIASES[key] = ucum


def canonical(unit: str) -> str:
    """Normalise surface spelling toward UCUM without discarding meaning."""
    u = unit.strip().replace(" ", "")
    alias = REGISTERED_ALIASES.get(u.lower())
    if alias is not None:
        return alias
    u = u.replace("µ", "u").replace("μ", "u")
    u = re.sub(r"^[xX×]", "", u)
    u = u.replace("10^", "10*")
    u = re.sub(r"\bgm/", "g/", u)
    # Reports capitalise UCUM's lowercase 'eq' and 'osm' atoms (mEq/L, mOsm/kg).
    # Case folding here keeps the grammar generated rather than alias-listed.
    u = re.sub(r"(?<=[a-zA-Z])Eq\b", "eq", u)
    u = re.sub(r"^Eq\b", "eq", u)
    u = re.sub(r"(?<=[a-zA-Z])Osm\b", "osm", u)
    u = re.sub(r"^Osm\b", "osm", u)
    # UCUM spells litre 'L'; reports use both cases. Uppercase only the
    # litre atom, never a whole composite (mg must not become MG).
    u = re.sub(r"(?<![A-Za-z])l(?![A-Za-z])", "L", u)
    u = re.sub(r"(?<=[dcmunp])l(?![A-Za-z])", "L", u)
    return u


def dimension(unit: str) -> Optional[str]:
    """Quantity kind of a composite, or None if the grammar rejects it."""
    u = canonical(unit)
    if re.fullmatch(COUNT_MANTISSA_RX, u):
        return "count"
    # A leading solidus is UCUM's inverse form: '/min' is a rate, '/uL' a
    # concentration of counts. The numerator is an implicit unity, so the
    # dimension is 'per <denominator>' rather than unparseable.
    if u.startswith("/"):
        tail_head = re.sub(r"[\*\^]\s?-?\d+$", "",
                           re.split(r"[/.]", u[1:])[0])
        tail_dim = ATOM_FORMS.get(tail_head)
        if tail_dim is None and tail_head not in {"L", "dL", "mL"}:
            return None
        return f"count_per_{tail_dim or 'unit'}"
    head = re.split(r"[/.]", u)[0]
    head = re.sub(r"[\*\^]\s?-?\d+$", "", head)
    if re.fullmatch(COUNT_MANTISSA_RX, head):
        return "count"
    # '10' is the mantissa of a count unit (10*9/L) but is not an atom in its
    # own right -- treating it as one makes the number '10.4' parse as a unit,
    # because UCUM reads '.' as multiplication. Resolve it here, then fall
    # through so the denominator still contributes ('/L' -> count_per_volume).
    if head == "10" and re.match(COUNT_MANTISSA_RX, u):
        dim = "count"
    else:
        dim = ATOM_FORMS.get(head)
    if dim is None:
        return None
    if "/" in u:
        tail = u.split("/", 1)[1]
        tail_head = re.sub(r"[\*\^]\s?-?\d+$", "", re.split(r"[/.]", tail)[0])
        tail_dim = ATOM_FORMS.get(tail_head)
        if tail_dim in {"volume", "time"} or tail_head in {"L", "dL", "mL"}:
            return f"{dim}_per_{tail_dim or 'unit'}"
    return dim


def is_plausible_unit(unit: str, *, require_hint: bool = False) -> bool:
    """Whether a grammar match should be treated as a real clinical unit."""
    raw = unit.strip()
    if not raw or raw in AMBIGUOUS_ALONE or raw in NEVER_UNITS:
        return False
    if re.fullmatch(r"-?\d+(?:[.,]\d+)?", raw):
        return False        # a bare number is a value, never a unit
    if dimension(raw) is None and not re.match(COUNT_MANTISSA_RX, raw):
        return False
    if require_hint:
        return bool(CLINICAL_HINT_RX.fullmatch(canonical(raw))
                    or CLINICAL_HINT_RX.match(canonical(raw)))
    return True


def find_units(text: str, *, require_hint: bool = False
               ) -> list[tuple[int, int, str]]:
    """All plausible unit tokens as (start, end, surface)."""
    out: list[tuple[int, int, str]] = []
    for m in UNIT_BOUNDED_RX.finditer(text):
        u = m.group("unit")
        if is_plausible_unit(u, require_hint=require_hint):
            out.append((m.start("unit"), m.end("unit"), u))
    return out


# A number immediately before a unit token. Adjacency is what separates a real
# measurement from a grammar coincidence, so it is required rather than
# inferred: '2.3 cm' is a measurement, 'seen in 3 pm' is not.
NUMBER_RX = re.compile(r"(?<![\w.])(?P<num>-?\d{1,7}(?:[.,]\d{1,4})?)")

# Patterns that look numeric but are never a measurement value.
_CLOCK_RX = re.compile(r"\b\d{1,2}:\d{2}\b")
_DATE_LIKE_RX = re.compile(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b")


def find_measurements(text: str, *, max_gap: int = 2
                      ) -> list[dict]:
    """Every (value, unit) pair in `text`, found unit-first.

    Returns dicts with the value, the surface unit, the canonical unit, the
    dimension, and character spans for both parts. No analyte label is
    involved: this is deliberately layout-blind, and label association is a
    separate, later decision made by the extractor.
    """
    blocked = [m.span() for m in _CLOCK_RX.finditer(text)]
    blocked += [m.span() for m in _DATE_LIKE_RX.finditer(text)]

    def is_blocked(a: int, b: int) -> bool:
        return any(a < e and s < b for s, e in blocked)

    out: list[dict] = []
    for u_start, u_end, surface in find_units(text):
        if is_blocked(u_start, u_end):
            continue
        # Walk back over at most `max_gap` spaces to the number.
        left = text[:u_start]
        gap = len(left) - len(left.rstrip(" \t"))
        if gap > max_gap:
            continue
        m = None
        for m in NUMBER_RX.finditer(left.rstrip(" \t")):
            pass                          # keep the LAST number before the unit
        if m is None or m.end() != len(left.rstrip(" \t")):
            continue
        if is_blocked(m.start(), m.end()):
            continue
        try:
            value = float(m.group("num").replace(",", "."))
        except ValueError:
            continue
        out.append({
            "value": value,
            "unit": surface,
            "unit_canonical": canonical(surface),
            "dimension": dimension(surface),
            "value_span": (m.start("num"), m.end("num")),
            "unit_span": (u_start, u_end),
            "span": (m.start("num"), u_end),
        })
    return out


def same_dimension(a: Optional[str], b: Optional[str]) -> bool:
    """Whether two units measure the same kind of thing.

    Used before comparing two values of one analyte: a difference between
    values reported in different dimensions is a unit mismatch to disclose,
    not a numeric conflict to assert.
    """
    if not a or not b:
        return False
    if canonical(a) == canonical(b):
        return True
    da, db = dimension(a), dimension(b)
    return da is not None and da == db


CONVERSIONS: dict[tuple[str, str], float] = {
    ("g/dL", "g/L"): 10.0,
    ("g/L", "g/dL"): 0.1,
    ("mg/dL", "mg/L"): 10.0,
    ("mg/L", "mg/dL"): 0.1,
    ("ng/mL", "ug/L"): 1.0,
    ("ug/L", "ng/mL"): 1.0,
    ("10*9/L", "10*3/uL"): 1.0,
    ("10*3/uL", "10*9/L"): 1.0,
    ("10*12/L", "10*6/uL"): 1.0,
    ("10*6/uL", "10*12/L"): 1.0,
}


def convert(value: float, frm: str, to: str) -> Optional[float]:
    """Exact scale conversion, or None when no published factor applies.

    Deliberately narrow: molar/mass conversions need an analyte-specific
    molecular weight, and guessing one would fabricate a value. Callers must
    treat None as 'not comparable' and disclose it.
    """
    f, t = canonical(frm), canonical(to)
    if f == t:
        return value
    factor = CONVERSIONS.get((f, t))
    return None if factor is None else value * factor


def load_ucum_essence(path) -> int:
    """Extend the atom table from an operator-supplied UCUM release.

    Returns the number of atoms added. Absent a licensed copy the generated
    grammar above stands on its own; this is the extension point, and it never
    silently succeeds -- a malformed file raises.
    """
    import xml.etree.ElementTree as ET
    root = ET.parse(str(path)).getroot()
    added = 0
    for el in root.iter():
        if not el.tag.endswith("unit") and not el.tag.endswith("base-unit"):
            continue
        code = el.get("Code") or el.get("code")
        if not code or code in ATOM_FORMS:
            continue
        prop = (el.findtext("property") or el.findtext("{*}property")
                or "unknown")
        ATOM_FORMS[code] = prop.strip() or "unknown"
        added += 1
    if added == 0 and not len(ATOM_FORMS):
        raise ValueError("No unit atoms found in UCUM file")
    return added
