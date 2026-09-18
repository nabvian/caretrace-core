"""Laboratory Pack — the CBC / chemistry vocabulary.

Unchanged in substance from the original medical lexicon; it is now one pack
among several rather than the only vocabulary. Concepts here are the numeric
laboratory analytes; other modalities live in sibling packs.
"""
from __future__ import annotations

from ..base import ClaimTypeDef, ConceptDef, Pack



CONCEPTS: dict[str, ConceptDef] = {
    "hemoglobin": ConceptDef(
        "hemoglobin", "Hemoglobin", "g/dL", 0.6, 0.06,
        ("hemoglobin", "haemoglobin", "hb", "hgb", "hemoglobin level",
         "haemoglobin level", "hb level"),
        (("gm/dl", "g/dL"), ("g/dl", "g/dL"), ("g / dl", "g/dL"),
         ("gm%", "g/dL"), ("g%", "g/dL")),
    ),
    "rbc": ConceptDef(
        "rbc", "RBC Count", "x10^12/L", 0.3, 0.07,
        ("rbc", "rbc count", "red blood cell count", "red cell count",
         "erythrocyte count"),
        (("million/ul", "x10^12/L"), ("10^12/l", "x10^12/L"),
         ("x10^12/l", "x10^12/L"), ("mill/cumm", "x10^12/L")),
    ),
    "hematocrit": ConceptDef(
        "hematocrit", "Hematocrit", "%", 2.0, 0.06,
        ("hematocrit", "haematocrit", "hct", "pcv", "packed cell volume"),
        (("percent", "%"), ("%", "%")),
    ),
    "mcv": ConceptDef(
        "mcv", "MCV", "fL", 3.0, 0.05,
        ("mcv", "mean corpuscular volume", "mean cell volume"),
        (("fl", "fL"), ("femtolitre", "fL")),
    ),
    "mch": ConceptDef(
        "mch", "MCH", "pg", 1.5, 0.06,
        ("mch", "mean corpuscular hemoglobin", "mean corpuscular haemoglobin"),
        (("pg", "pg"),),
    ),
    "mchc": ConceptDef(
        "mchc", "MCHC", "g/dL", 1.5, 0.05,
        ("mchc", "mean corpuscular hemoglobin concentration",
         "mean corpuscular haemoglobin concentration"),
        (("g/dl", "g/dL"), ("gm/dl", "g/dL")),
    ),
    "rdw": ConceptDef(
        "rdw", "RDW", "%", 1.5, 0.08,
        ("rdw", "rdw-cv", "red cell distribution width"),
        (("%", "%"),),
    ),
    "wbc": ConceptDef(
        "wbc", "WBC Count", "x10^9/L", 1.0, 0.15,
        ("wbc", "wbc count", "white blood cell count", "tlc",
         "total leucocyte count", "total leukocyte count", "leucocyte count"),
        (("/ul", "x10^9/L"), ("cells/ul", "x10^9/L"), ("cumm", "x10^9/L"),
         ("/cumm", "x10^9/L"), ("10^9/l", "x10^9/L"), ("x10^9/l", "x10^9/L")),
    ),
    "platelets": ConceptDef(
        "platelets", "Platelet Count", "x10^9/L", 30.0, 0.15,
        ("platelets", "platelet", "platelet count", "plt", "thrombocyte count"),
        (("/ul", "x10^9/L"), ("lakh/cumm", "x10^9/L"), ("10^9/l", "x10^9/L"),
         ("x10^9/l", "x10^9/L"), ("/cumm", "x10^9/L")),
    ),
    "ferritin": ConceptDef(
        "ferritin", "Serum Ferritin", "ng/mL", 5.0, 0.15,
        ("ferritin", "serum ferritin", "ferritin level"),
        (("ng/ml", "ng/mL"), ("ug/l", "ng/mL"), ("mcg/l", "ng/mL")),
    ),
    "creatinine": ConceptDef(
        "creatinine", "Serum Creatinine", "mg/dL", 0.2, 0.15,
        ("creatinine", "serum creatinine", "s. creatinine", "creat"),
        (("mg/dl", "mg/dL"), ("mg%", "mg/dL")),
    ),
    "glucose": ConceptDef(
        "glucose", "Glucose", "mg/dL", 15.0, 0.12,
        ("glucose", "blood glucose", "fasting glucose", "fasting blood sugar",
         "fbs", "random blood sugar", "rbs", "plasma glucose"),
        (("mg/dl", "mg/dL"), ("mg%", "mg/dL")),
    ),
}

# Reverse index: surface synonym -> concept key. Longest-first at match time.

UNIT_ALIAS_INDEX: dict[str, dict[str, str]] = {
    k: {a.lower(): canon for a, canon in cd.unit_aliases}
    for k, cd in CONCEPTS.items()
}


# --------------------------------------------------------------------------
# Medication vocabulary — arbitrary drug names supported; these are only
# normalization aids for names that recur in more than one spelling.
# --------------------------------------------------------------------------
MEDICATION_SYNONYMS: dict[str, str] = {
    "ferrous sulfate": "ferrous sulfate",
    "ferrous sulphate": "ferrous sulfate",
    "fe sulfate": "ferrous sulfate",
    "iron (ferrous sulfate)": "ferrous sulfate",
    "ferrous ascorbate": "ferrous ascorbate",
    "folic acid": "folic acid",
    "vitamin b12": "vitamin b12",
    "cyanocobalamin": "vitamin b12",
    "pantoprazole": "pantoprazole",
    "paracetamol": "paracetamol",
    "acetaminophen": "paracetamol",
    "vitamin c": "ascorbic acid",
    "ascorbic acid": "ascorbic acid",
}

MEDICATION_CLASS_TERMS: dict[str, tuple[str, ...]] = {
    "oral iron": ("ferrous sulfate", "ferrous ascorbate", "iron"),
}


# --------------------------------------------------------------------------
# Claim types and the evidence each requires.
#
# `requires_any`: concepts that would constitute located supporting evidence.
# `supportive_direction`: how a value relates to the claim, used ONLY to label
# a located observation as supporting/contradicting the documented claim. This
# never asserts a diagnosis — it reports whether the record contains the test
# the claim would rest on.
# --------------------------------------------------------------------------

CLAIM_TYPES: tuple[ClaimTypeDef, ...] = (
    ClaimTypeDef(
        key="IRON_DEFICIENCY",
        label="Iron deficiency",
        patterns=("iron deficiency confirmed", "iron deficiency anaemia confirmed",
                  "iron deficiency anemia confirmed", "confirmed iron deficiency",
                  "iron deficiency established", "iron deficiency documented"),
        # "transferrin_saturation" is an alias of "tsat" in the label map; listing
        # only the canonical key keeps the missing-evidence list one row per test.
        requires_any=("ferritin", "tsat", "serum_iron"),
        requires_labels=("Serum Ferritin", "Transferrin saturation (TSAT)",
                         "Serum iron studies"),
        supportive_direction=(("ferritin", "lt", 30.0),),
    ),
    ClaimTypeDef(
        key="ANEMIA_PRESENT",
        label="Anemia documented",
        patterns=("anaemia", "anemia", "anaemic", "anemic"),
        requires_any=("hemoglobin",),
        requires_labels=("Hemoglobin",),
        supportive_direction=(("hemoglobin", "lt", 13.0),),
    ),
    ClaimTypeDef(
        key="MICROCYTOSIS",
        label="Microcytosis",
        patterns=("microcytic", "microcytosis", "microcytic hypochromic"),
        requires_any=("mcv",),
        requires_labels=("MCV",),
        supportive_direction=(("mcv", "lt", 80.0),),
    ),
    ClaimTypeDef(
        key="HB_NORMALIZED",
        label="Hemoglobin normalized",
        patterns=("hemoglobin normalised", "hemoglobin normalized",
                  "haemoglobin normalised", "haemoglobin normalized",
                  "hb normalised", "hb normalized", "haemoglobin has normalised"),
        requires_any=("hemoglobin",),
        requires_labels=("Hemoglobin",),
        supportive_direction=(("hemoglobin", "gt", 13.0),),
    ),
    ClaimTypeDef(
        key="RENAL_FUNCTION_NORMAL",
        label="Renal function normal",
        patterns=("renal function normal", "renal function is normal",
                  "normal renal function", "kidney function normal"),
        requires_any=("creatinine",),
        requires_labels=("Serum Creatinine",),
        supportive_direction=(("creatinine", "lt", 1.3),),
    ),
    ClaimTypeDef(
        key="THALASSEMIA_TRAIT_EXCLUDED",
        label="Thalassemia trait excluded",
        patterns=("thalassaemia trait excluded", "thalassemia trait excluded",
                  "thalassaemia excluded", "thalassemia excluded",
                  "haemoglobinopathy excluded", "hemoglobinopathy excluded"),
        requires_any=("hb_electrophoresis", "hplc"),
        requires_labels=("Hemoglobin electrophoresis / HPLC",),
    ),
    ClaimTypeDef(
        key="GI_BLEED_EXCLUDED",
        label="GI blood loss excluded",
        patterns=("gi blood loss excluded", "no evidence of gi bleed",
                  "gastrointestinal blood loss excluded", "occult blood negative"),
        requires_any=("fecal_occult_blood", "endoscopy"),
        requires_labels=("Faecal occult blood test", "Endoscopy report"),
    ),
)

# Concepts a claim may require that the MVP does not extract as observations.
# Naming them explicitly is what lets the gap engine say what was NOT located
# rather than staying silent.
UNSUPPORTED_CONCEPT_LABELS: dict[str, str] = {
    "tsat": "Transferrin saturation (TSAT)",
    "serum_iron": "Serum iron",
    "transferrin_saturation": "Transferrin saturation (TSAT)",
    "hb_electrophoresis": "Hemoglobin electrophoresis",
    "hplc": "HPLC",
    "fecal_occult_blood": "Faecal occult blood test",
    "endoscopy": "Endoscopy report",
}


# --------------------------------------------------------------------------
# Phrases that indicate an expected follow-up record.
# --------------------------------------------------------------------------
FOLLOWUP_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"repeat\s+(?:the\s+)?(cbc|complete blood count|haemogram|hemogram)"
     r"[^.\n]{0,60}", "Repeat CBC"),
    (r"repeat\s+(?:serum\s+)?ferritin[^.\n]{0,60}", "Repeat ferritin"),
    (r"review\s+(?:with|after)\s+[^.\n]{0,60}", "Review with results"),
    (r"(?:refer|referral)\s+(?:to|for)\s+([a-z ]{3,40})", "Referral"),
)

# Phrases that reference an external document.
# A citation is a record pointing AT another document, so every pattern must be
# anchored on a citing verb. A bare noun phrase such as r"\bCT report\b" also
# matches a CT report's own title page, which manufactures a citation of the
# document by itself. Imaging citations are declared by the Imaging Pack; what
# remains here are the report kinds a laboratory record cites.
_CITE = (r"\b(?:as\s+(?:described|reported|noted|detailed)\s+(?:in|on)|"
         r"see|refer\s+to|per|awaiting|pending|correlate\s+with)\s+"
         r"(?:the\s+)?")

DOCUMENT_REFERENCE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (_CITE + r"endoscopy\s+report\b", "Endoscopy report", "OTHER"),
    (_CITE + r"biopsy\s+report\b", "Biopsy report", "PATHOLOGY_REPORT"),
    (_CITE + r"histopathology\s+report\b", "Histopathology report",
     "PATHOLOGY_REPORT"),
    (_CITE + r"peripheral\s+smear\s+report\b", "Peripheral smear report",
     "PATHOLOGY_REPORT"),
)


# ---------------------------------------------------------------------------
# Pack policy: the time windows the deterministic engine is configured with.
# These are declared here, not hard-coded in the engine, so that swapping the
# pack changes the audit policy without touching core code.
# ---------------------------------------------------------------------------

#: Two records of the same concept within this many days are treated as
#: describing the same clinical episode, so a material difference between them
#: is a contradiction rather than a documented change over time.

CONFLICT_WINDOW_DAYS: dict[str, int] = {
    "hemoglobin": 2,
    "platelets": 2,
    "hematocrit": 2,
    "rbc": 2,
    "mcv": 7,          # red-cell indices move slowly
    "mch": 7,
    "mchc": 7,
    "rdw": 7,
    "wbc": 2,
    "ferritin": 14,    # an acute-phase reactant, but not a same-week mover
    "creatinine": 2,
    "glucose": 1,
}

#: How far back from a claim the engine will look for supporting evidence.
#: Evidence dated AFTER a claim is never treated as supporting it.

CLAIM_LOOKBACK_DAYS: dict[str, int] = {
    "IRON_DEFICIENCY": 180,
    "ANEMIA_PRESENT": 90,
    "MICROCYTOSIS": 90,
    "HB_NORMALIZED": 7,            # a discharge statement refers to that stay
    "RENAL_FUNCTION_NORMAL": 30,
    "THALASSEMIA_TRAIT_EXCLUDED": 365,
    "GI_BLEED_EXCLUDED": 365,
}

#: Expected interval for a documented follow-up instruction, in days, keyed by
#: the FOLLOWUP_PATTERNS label. Used only to decide whether a follow-up is even
#: due yet within the span of the uploaded record.
FOLLOWUP_EXPECTATIONS: dict[str, tuple[int, str | None]] = {
    # label: (expected interval days, expected document type or None)
    "Repeat CBC": (56, "LAB_REPORT"),
    "Repeat ferritin": (56, "LAB_REPORT"),
    "Review with results": (42, None),
    "Referral": (60, None),
}


PACK = Pack(
    key="laboratory", label="Laboratory Pack", modality="LABORATORY",
    concepts=CONCEPTS, claim_types=CLAIM_TYPES,
    medication_synonyms=MEDICATION_SYNONYMS,
    medication_class_terms=MEDICATION_CLASS_TERMS,
    unsupported_concept_labels=UNSUPPORTED_CONCEPT_LABELS,
    followup_patterns=FOLLOWUP_PATTERNS,
    document_reference_patterns=DOCUMENT_REFERENCE_PATTERNS,
    conflict_window_days=CONFLICT_WINDOW_DAYS,
    claim_lookback_days=CLAIM_LOOKBACK_DAYS,
    followup_expectations=FOLLOWUP_EXPECTATIONS,
    document_cues=(
        ("LAB_REPORT", ("complete blood count", "laboratory summary",
                        "iron studies", "cumulative laboratory")),
    ),
    filename_cues=(
        ("LAB_REPORT", ("cbc", "lab", "ferritin", "laboratory")),
    ),
)
