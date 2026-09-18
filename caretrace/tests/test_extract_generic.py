"""Layout-agnostic extraction.

The requirement: no parser may be wired to a particular laboratory's layout.
These tests hold the SAME analytes in many different formats and assert every
format yields the same values. If a change makes extraction depend on one
report's shape, the variant table below breaks.
"""
from __future__ import annotations

import pytest

from caretrace.core import units as U
from caretrace.core.extract_generic import (
    Measurement, extract_measurements, extract_sections, is_furniture,
    section_map)
from caretrace.core.normalize import is_unmapped, resolve_label

# Seven layouts, none of them encoded in the extractor. Each must yield
# hemoglobin 9.2 g/dL and MCV 68 fL.
LAYOUTS = {
    "row_with_parenthesised_range": (
        "COMPLETE BLOOD COUNT\n"
        "Hemoglobin        9.2 g/dL     (13.0 - 17.0)\n"
        "MCV               68.0 fL      (80 - 100)\n"),
    "columnar_unit_in_own_column": (
        "Test          Result   Unit     Ref Range\n"
        "Haemoglobin    9.2     g/dL     13.0-17.0\n"
        "M.C.V.         68.0    fL       80-100\n"),
    "inline_pipe_delimited": "Hb: 9.2 g/dL | MCV: 68 fL\n",
    "dotted_leaders_with_flags": (
        "1) Hemoglobin (Hb) ..... 9.2 g/dL  L\n"
        "2) Mean Corpuscular Volume ... 68 fL  L\n"),
    "narrative_prose": (
        "The patient's haemoglobin was 9.2 g/dL with an MCV of 68 fL "
        "on admission.\n"),
    "reference_before_result": (
        "Hemoglobin   Ref: 13.0-17.0 g/dL   Result: 9.2 g/dL\n"
        "MCV   Ref: 80-100 fL   Result: 68 fL\n"),
    "tab_separated": ("Hemoglobin\t9.2\tg/dL\t13.0-17.0\n"
                      "MCV\t68.0\tfL\t80-100\n"),
}


@pytest.mark.parametrize("name,text", sorted(LAYOUTS.items()))
def test_same_analytes_recovered_from_every_layout(name, text):
    got = {(m.value, m.unit_canonical) for m in extract_measurements(text)}
    assert (9.2, "g/dL") in got, f"{name}: hemoglobin value lost"
    assert (68.0, "fL") in got, f"{name}: MCV value lost"


@pytest.mark.parametrize("name,text", sorted(LAYOUTS.items()))
def test_labels_resolve_to_the_same_concepts_from_every_layout(name, text):
    keys = set()
    for m in extract_measurements(text):
        k, _disp, _meth = resolve_label(m.label)
        if k:
            keys.add(k)
    assert {"hemoglobin", "mcv"} <= keys, f"{name}: got {keys}"


def test_reference_range_bounds_are_never_read_as_results():
    ms = extract_measurements(
        "Hemoglobin        9.2 g/dL     (13.0 - 17.0)\n")
    assert [m.value for m in ms] == [9.2]
    assert ms[0].reference_range and "13.0" in ms[0].reference_range


def test_printed_abnormality_flag_is_captured_as_printed():
    ms = extract_measurements("Hemoglobin  9.2 g/dL  L\n")
    assert ms[0].flag == "L"


def test_clock_times_and_dates_are_not_measurements():
    assert extract_measurements("Appointment at 14:30 on 2026-01-18\n") == []
    assert extract_measurements("Seen in clinic at 3 pm\n") == []


def test_unit_grammar_is_generated_not_enumerated():
    """mmol/L and pmol/mL are never listed anywhere, but must parse."""
    for unit in ("mmol/L", "pmol/mL", "umol/L", "mEq/L", "ug/dL", "kU/L"):
        assert U.dimension(unit) is not None, unit
    ms = extract_measurements("Glucose 5.4 mmol/L\nVitamin D 42 nmol/L\n")
    assert {(m.value, m.unit_canonical) for m in ms} == {
        (5.4, "mmol/L"), (42.0, "nmol/L")}


def test_unknown_analyte_is_kept_and_marked_unrecognised():
    """A concept outside the vocabulary must not be silently dropped."""
    ms = extract_measurements("Anti-CCP antibody      42 U/mL\n")
    assert len(ms) == 1 and ms[0].value == 42.0
    key, display, method = resolve_label(ms[0].label)
    assert method == "UNRECOGNISED"
    assert is_unmapped(key)
    assert "Anti-CCP" in display        # original wording preserved


def test_non_laboratory_modalities_extract_too():
    """ECG intervals and imaging measurements, not just laboratory values."""
    ecg = extract_measurements("PR interval 168 ms, QRS 92 ms, QTc 465 ms\n")
    assert {m.value for m in ecg} == {168.0, 92.0, 465.0}
    assert {m.dimension for m in ecg} == {"time"}
    ct = extract_measurements("A 2.3 cm hypodense lesion in segment VI.\n")
    assert ct and ct[0].value == 2.3 and ct[0].dimension == "length"


def test_document_furniture_is_not_treated_as_an_analyte():
    for label in ("Page", "MRN", "Report No", "Reference Range",
                  "Sample Collected", "Technician"):
        assert is_furniture(label), label
    assert not is_furniture("Hemoglobin")
    assert not is_furniture("Ferritin")


def test_sections_are_found_by_heading_shape_not_heading_text():
    a = ("CLINICAL HISTORY:\nAnaemia under evaluation.\n\n"
         "FINDINGS:\nLiver normal. No biliary dilatation.\n\n"
         "IMPRESSION:\nIndeterminate hepatic lesion.\n")
    b = ("Indication\nAnaemia under evaluation.\n\n"
         "Observations\nLiver normal. No biliary dilatation.\n\n"
         "Conclusion\nIndeterminate hepatic lesion.\n")
    for text in (a, b):
        roles = section_map(text)
        assert {"INDICATION", "FINDINGS", "IMPRESSION"} <= set(roles)
        assert "Liver normal" in roles["FINDINGS"]


def test_unmapped_heading_is_preserved_not_discarded():
    secs = extract_sections(
        "SPECIAL REMARKS\nSpecimen haemolysed on receipt.\n")
    assert secs and secs[0].role == "OTHER"
    assert secs[0].heading == "SPECIAL REMARKS"
    assert "haemolysed" in secs[0].text


def test_every_measurement_carries_its_source_line():
    for text in LAYOUTS.values():
        for m in extract_measurements(text):
            assert m.source_text, "provenance line missing"
            assert str(m.value).rstrip("0").rstrip(".") in m.line.replace(
                ",", ".") or str(int(m.value)) in m.line


def test_unit_dimension_mismatch_is_not_comparable():
    """Two values of one analyte in different dimensions are not a numeric
    conflict; the engine must be able to tell."""
    assert U.same_dimension("g/dL", "g/L")
    assert not U.same_dimension("g/dL", "fL")
    assert U.convert(9.2, "g/dL", "g/L") == pytest.approx(92.0)
    assert U.convert(5.0, "mmol/L", "g/dL") is None   # no factor -> refuse
