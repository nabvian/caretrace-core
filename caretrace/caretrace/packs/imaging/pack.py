"""Imaging Pack — X-ray, CT, MRI, ultrasound reports.

Imaging reports are mostly prose. What CARETRACE can audit deterministically is
(a) the measurements radiologists do state numerically -- lesion size, organ
dimensions, calcium score -- and (b) the presence/absence findings they state as
status text. Both are documented statements; neither is interpreted here.
"""
from __future__ import annotations

from ..base import (ClaimTypeDef, ConceptDef, Pack,
                    StatusConceptDef as SC, StatusValue as SV)

M = "IMAGING"

CONCEPTS = {
    "lesion_size": ConceptDef(
        "lesion_size", "Lesion / nodule size", "mm", 2.0, 0.15,
        ("lesion", "lesion size", "nodule", "nodule size", "mass", "mass size",
         "largest lesion", "index lesion", "target lesion", "opacity"),
        (("cm", "mm"), ("millimetre", "mm"), ("millimeter", "mm")), M),
    "spleen_size": ConceptDef(
        "spleen_size", "Spleen size", "cm", 1.0, 0.10,
        ("spleen", "spleen size", "splenic length", "spleen span"),
        (("mm", "cm"),), M),
    "liver_size": ConceptDef(
        "liver_size", "Liver span", "cm", 1.0, 0.10,
        ("liver span", "liver size", "hepatic span", "craniocaudal liver"),
        (("mm", "cm"),), M),
    "kidney_size": ConceptDef(
        "kidney_size", "Kidney length", "cm", 0.8, 0.10,
        ("kidney length", "renal length", "right kidney", "left kidney"),
        (("mm", "cm"),), M),
    "cortical_thickness": ConceptDef(
        "cortical_thickness", "Renal cortical thickness", "mm", 1.5, 0.15,
        ("cortical thickness", "renal cortical thickness"), (("cm", "mm"),), M),
    "calcium_score": ConceptDef(
        "calcium_score", "Coronary calcium score", "1", 20.0, 0.20,
        ("calcium score", "agatston score", "coronary calcium score",
         "agatston"), (), M),
}

STATUS_CONCEPTS = {
    "acute_infarct": SC("acute_infarct", "Acute infarct", (
        SV("ABSENT", "No acute infarct",
           ("no acute infarct", "no infarct", "no acute ischaemic change",
            "no acute ischemic change", "no evidence of infarct"), False),
        SV("PRESENT", "Acute infarct present",
           ("acute infarct", "infarct present", "acute ischaemic change",
            "acute ischemic change")),
    ), M),
    "hemorrhage": SC("hemorrhage", "Intracranial haemorrhage", (
        SV("ABSENT", "No haemorrhage",
           ("no haemorrhage", "no hemorrhage", "no intracranial bleed",
            "no intracranial haemorrhage", "no acute bleed"), False),
        SV("PRESENT", "Haemorrhage present",
           ("haemorrhage present", "hemorrhage present", "intracranial bleed",
            "acute haemorrhage", "acute hemorrhage")),
    ), M),
    "consolidation": SC("consolidation", "Pulmonary consolidation", (
        SV("ABSENT", "No consolidation", ("no consolidation",), False),
        SV("PRESENT", "Consolidation present",
           ("consolidation present", "patchy consolidation",
            "lobar consolidation", "areas of consolidation")),
    ), M),
    "pleural_effusion": SC("pleural_effusion", "Pleural effusion", (
        SV("ABSENT", "No pleural effusion",
           ("no pleural effusion", "no effusion"), False),
        SV("PRESENT", "Pleural effusion present",
           ("pleural effusion present", "small pleural effusion",
            "effusion noted", "pleural effusion seen")),
    ), M),
    "metastasis": SC("metastasis", "Metastatic disease", (
        SV("ABSENT", "No metastasis",
           ("no metastasis", "no metastases", "no evidence of metastasis",
            "no metastatic disease"), False),
        SV("PRESENT", "Metastases present",
           ("metastases present", "metastatic deposits",
            "metastatic disease", "metastasis present")),
    ), M),
    "fracture": SC("fracture", "Fracture", (
        SV("ABSENT", "No fracture", ("no fracture", "no acute fracture"), False),
        SV("PRESENT", "Fracture present", ("fracture present", "acute fracture")),
    ), M),
}

CLAIM_TYPES = (
    ClaimTypeDef(
        key="IMAGING_NORMAL",
        label="Imaging reported normal",
        patterns=("imaging is normal", "imaging normal", "scan is normal",
                  "no abnormality detected", "study is unremarkable",
                  "unremarkable study"),
        requires_any=tuple(STATUS_CONCEPTS),
        requires_labels=("A radiology report stating the findings",),
        supportive_status_polarity=False,
        modality=M),
    ClaimTypeDef(
        key="LESION_STABLE",
        label="Lesion described as stable",
        patterns=("lesion is stable", "stable disease", "no interval change",
                  "lesion unchanged", "stable in size"),
        requires_any=("lesion_size",),
        requires_labels=("A prior imaging measurement of the same lesion",),
        modality=M),
    ClaimTypeDef(
        key="SPLENOMEGALY",
        label="Splenomegaly documented",
        patterns=("splenomegaly", "enlarged spleen", "spleen is enlarged"),
        requires_any=("spleen_size",),
        requires_labels=("Spleen size on imaging",),
        supportive_direction=(("spleen_size", "gt", 13.0),),
        modality=M),
)

UNSUPPORTED_CONCEPT_LABELS = {
    "ct_report": "CT report",
    "mri_report": "MRI report",
    "xray_report": "X-ray report",
    "ultrasound_report": "Ultrasound report",
    "prior_imaging": "Prior imaging study for comparison",
}

# Imaging reports routinely defer to another study. Naming the referenced
# document is what lets the gap engine report it as not uploaded.
DOCUMENT_REFERENCE_PATTERNS = (
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(ct(?:\s+\w+)?)\s+(?:report|scan|study)", "CT report", "IMAGING_REPORT"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(mri)\s+(?:report|scan|study)", "MRI report", "IMAGING_REPORT"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(?:chest\s+)?(x-?ray|radiograph)\s*(?:report)?", "X-ray report", "IMAGING_REPORT"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(ultrasound|usg|sonography)\s*(?:report)?", "Ultrasound report", "IMAGING_REPORT"),
    (r"\bcompared (?:to|with) (?:the )?prior (?:study|imaging|scan)", "Prior imaging study", "IMAGING_REPORT"),
)

FOLLOWUP_PATTERNS = (
    (r"repeat (?:the )?(?:ct|scan|imaging) in (\d+)\s*(?:week|month)", "IMAGING_REPORT"),
    (r"interval imaging in (\d+)\s*(?:week|month)", "IMAGING_REPORT"),
    (r"follow-?up (?:ct|mri|imaging|scan)", "IMAGING_REPORT"),
)

PACK = Pack(
    key="imaging", label="Imaging Pack", modality=M,
    concepts=CONCEPTS, claim_types=CLAIM_TYPES,
    unsupported_concept_labels=UNSUPPORTED_CONCEPT_LABELS,
    followup_patterns=FOLLOWUP_PATTERNS,
    document_reference_patterns=DOCUMENT_REFERENCE_PATTERNS,
    conflict_window_days={"lesion_size": 30, "spleen_size": 30, "liver_size": 30,
                          "kidney_size": 30, "calcium_score": 365},
    claim_lookback_days={"IMAGING_NORMAL": 180, "LESION_STABLE": 365,
                         "SPLENOMEGALY": 180},
    status_concepts=STATUS_CONCEPTS,
    document_cues=(
        ("IMAGING_REPORT", ("ct report", "ultrasound report", "mri brain",
                            "mri report", "chest radiograph", "chest x-ray",
                            "radiograph report", "digital radiography",
                            "ct abdomen", "accession", "radiodiagnosis")),
    ),
    filename_cues=(
        ("IMAGING_REPORT", ("xray", "x-ray", "mri", "ct_", "_ct", "ultrasound",
                            "radiograph", "imaging")),
    ),
)
