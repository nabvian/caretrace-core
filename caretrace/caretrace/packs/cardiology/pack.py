"""Cardiology Pack — ECG and echocardiography reports.

ECGs report interval measurements numerically and rhythm as a status statement.
Echo reports add chamber measurements and ejection fraction.
"""
from __future__ import annotations

from ..base import (ClaimTypeDef, ConceptDef, Pack,
                    StatusConceptDef as SC, StatusValue as SV)

M = "CARDIOLOGY"

CONCEPTS = {
    "heart_rate": ConceptDef(
        "heart_rate", "Heart rate", "/min", 8.0, 0.12,
        ("heart rate", "hr", "ventricular rate", "pulse rate", "rate"),
        (("bpm", "/min"), ("beats/min", "/min"), ("beats per minute", "/min")), M),
    "pr_interval": ConceptDef(
        "pr_interval", "PR interval", "ms", 20.0, 0.12,
        ("pr interval", "pr"), (("s", "ms"), ("sec", "ms"), ("msec", "ms")), M),
    "qrs_duration": ConceptDef(
        "qrs_duration", "QRS duration", "ms", 15.0, 0.12,
        ("qrs duration", "qrs", "qrs width"),
        (("s", "ms"), ("msec", "ms")), M),
    "qt_interval": ConceptDef(
        "qt_interval", "QT interval", "ms", 25.0, 0.10,
        ("qt interval", "qt"), (("s", "ms"), ("msec", "ms")), M),
    "qtc_interval": ConceptDef(
        "qtc_interval", "QTc interval", "ms", 25.0, 0.10,
        ("qtc", "qtc interval", "corrected qt", "qtcb", "qtcf"),
        (("s", "ms"), ("msec", "ms")), M),
    "ejection_fraction": ConceptDef(
        "ejection_fraction", "Left ventricular ejection fraction", "%", 5.0, 0.10,
        ("ejection fraction", "lvef", "ef", "left ventricular ejection fraction"),
        (("percent", "%"),), M),
    "lv_diameter": ConceptDef(
        "lv_diameter", "LV end-diastolic diameter", "mm", 4.0, 0.10,
        ("lvedd", "lv end diastolic diameter", "lv internal diameter"),
        (("cm", "mm"),), M),
    "iv_septum": ConceptDef(
        "iv_septum", "Interventricular septal thickness", "mm", 2.0, 0.15,
        ("ivs", "interventricular septum", "septal thickness"), (("cm", "mm"),), M),
}

STATUS_CONCEPTS = {
    "rhythm": SC("rhythm", "Cardiac rhythm", (
        SV("SINUS", "Sinus rhythm", ("sinus rhythm", "normal sinus rhythm")),
        SV("AF", "Atrial fibrillation", ("atrial fibrillation", "af with",)),
        SV("FLUTTER", "Atrial flutter", ("atrial flutter",)),
        SV("SINUS_TACHY", "Sinus tachycardia", ("sinus tachycardia",)),
        SV("SINUS_BRADY", "Sinus bradycardia", ("sinus bradycardia",)),
        SV("PACED", "Paced rhythm", ("paced rhythm", "pacemaker rhythm")),
    ), M),
    "st_changes": SC("st_changes", "ST segment changes", (
        SV("ABSENT", "No ST changes",
           ("no st changes", "no acute st-t changes", "no st-t changes",
            "no ischaemic st changes"), False),
        SV("DEPRESSION", "ST depression", ("st depression",)),
        SV("ELEVATION", "ST elevation", ("st elevation",)),
        SV("NONSPECIFIC", "Nonspecific ST changes", ("nonspecific st changes",)),
    ), M),
    "t_wave": SC("t_wave", "T wave morphology", (
        SV("NORMAL", "No T wave inversion", ("no t wave inversion",), False),
        SV("INVERSION", "T wave inversion", ("t wave inversion", "inverted t waves")),
        SV("FLATTENED", "Flattened T waves", ("flattened t waves",)),
    ), M),
    "conduction_block": SC("conduction_block", "Conduction block", (
        SV("ABSENT", "No conduction block",
           ("no conduction block", "no bundle branch block"), False),
        SV("RBBB", "Right bundle branch block",
           ("right bundle branch block", "rbbb", "incomplete rbbb")),
        SV("LBBB", "Left bundle branch block", ("left bundle branch block", "lbbb")),
        SV("AVB1", "First degree AV block", ("first degree av block",)),
    ), M),
    "valve_status": SC("valve_status", "Valvular findings", (
        SV("NORMAL", "No valvular abnormality",
           ("no valvular abnormality", "valves are normal"), False),
        SV("MR", "Mitral regurgitation",
           ("mitral regurgitation", "trivial mitral regurgitation")),
        SV("AS", "Aortic stenosis", ("aortic stenosis",)),
    ), M),
}

CLAIM_TYPES = (
    ClaimTypeDef(
        key="ECG_NORMAL",
        label="ECG reported normal",
        patterns=("ecg is normal", "normal ecg", "ecg within normal limits",
                  "electrocardiogram normal"),
        requires_any=("rhythm", "heart_rate", "qrs_duration"),
        requires_labels=("An ECG report stating rhythm and intervals",),
        supportive_status_polarity=False,
        modality=M),
    ClaimTypeDef(
        key="LV_FUNCTION_NORMAL",
        label="LV function reported normal",
        patterns=("lv function normal", "normal lv function",
                  "normal left ventricular function", "ef preserved",
                  "preserved ejection fraction"),
        requires_any=("ejection_fraction",),
        requires_labels=("Ejection fraction on echocardiography",),
        supportive_direction=(("ejection_fraction", "gt", 50.0),),
        modality=M),
    ClaimTypeDef(
        key="QT_PROLONGED",
        label="QT prolongation documented",
        patterns=("prolonged qt", "qt prolongation", "long qt"),
        requires_any=("qtc_interval", "qt_interval"),
        requires_labels=("QTc measurement on ECG",),
        supportive_direction=(("qtc_interval", "gt", 450.0),),
        modality=M),
)

UNSUPPORTED_CONCEPT_LABELS = {
    "ecg_report": "ECG report",
    "echo_report": "Echocardiography report",
    "holter": "Holter / ambulatory ECG report",
    "stress_test": "Stress test report",
}

DOCUMENT_REFERENCE_PATTERNS = (
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(ecg|electrocardiogram)\s*(?:report)?", "ECG report", "OTHER"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(echo(?:cardiogram|cardiography)?)\s*(?:report)?",
     "Echocardiography report", "OTHER"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(holter)\s*(?:report|study)?", "Holter / ambulatory ECG report", "OTHER"),
)

FOLLOWUP_PATTERNS = (
    (r"repeat ecg in (\d+)\s*(?:week|month|day)", "OTHER"),
    (r"repeat echo(?:cardiogram)? in (\d+)\s*(?:week|month)", "OTHER"),
)

PACK = Pack(
    key="cardiology", label="Cardiology Pack", modality=M,
    concepts=CONCEPTS, claim_types=CLAIM_TYPES,
    unsupported_concept_labels=UNSUPPORTED_CONCEPT_LABELS,
    followup_patterns=FOLLOWUP_PATTERNS,
    document_reference_patterns=DOCUMENT_REFERENCE_PATTERNS,
    conflict_window_days={"heart_rate": 1, "ejection_fraction": 30,
                          "qtc_interval": 2, "pr_interval": 2, "qrs_duration": 2},
    claim_lookback_days={"ECG_NORMAL": 90, "LV_FUNCTION_NORMAL": 180,
                         "QT_PROLONGED": 30},
    status_concepts=STATUS_CONCEPTS,
    document_cues=(
        ("ECG_REPORT", ("electrocardiogram", "12-lead ecg", "ecg report",
                        "pr interval", "qtc (bazett)")),
    ),
    filename_cues=(("ECG_REPORT", ("ecg", "ekg")),),
)
