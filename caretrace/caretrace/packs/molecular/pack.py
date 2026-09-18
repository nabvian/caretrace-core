"""Molecular Pack — genetic, molecular and immunoassay reports.

Molecular reports mix quantitative results (viral load, expression ratios) with
categorical calls (variant detected / not detected, positive / negative). The
categorical call is the clinically load-bearing statement, so it is modelled as
a status concept rather than forced into a number.
"""
from __future__ import annotations

from ..base import (ClaimTypeDef, ConceptDef, Pack,
                    StatusConceptDef as SC, StatusValue as SV)

M = "MOLECULAR"

CONCEPTS = {
    "viral_load": ConceptDef(
        "viral_load", "Viral load", "/mL", 0.0, 0.50,
        ("viral load", "hbv dna", "hcv rna", "hiv rna", "copies",
         "quantitative pcr", "pcr quantitative"),
        (("copies/ml", "/mL"), ("iu/ml", "/mL"), ("cop/ml", "/mL")), M),
    "ct_value": ConceptDef(
        "ct_value", "PCR cycle threshold (Ct)", "1", 3.0, 0.10,
        ("ct value", "cycle threshold", "ct"), (), M),
    "variant_allele_fraction": ConceptDef(
        "variant_allele_fraction", "Variant allele fraction", "%", 5.0, 0.20,
        ("variant allele fraction", "vaf", "allele fraction",
         "allele frequency"), (("percent", "%"),), M),
    "tumor_mutational_burden": ConceptDef(
        "tumor_mutational_burden", "Tumour mutational burden", "1", 2.0, 0.20,
        ("tumour mutational burden", "tumor mutational burden", "tmb",
         "mutations/mb", "mutational burden"), (), M),
    "microsatellite_score": ConceptDef(
        "microsatellite_score", "Microsatellite instability score", "%", 5.0, 0.20,
        ("msi score", "microsatellite instability score", "msi"),
        (("percent", "%"),), M),
    "her2_ratio": ConceptDef(
        "her2_ratio", "HER2/CEP17 ratio", "1", 0.3, 0.15,
        ("her2/cep17 ratio", "her2 ratio", "her2 cep17"), (), M),
}

STATUS_CONCEPTS = {
    "variant_call": SC("variant_call", "Variant call", (
        SV("NONE", "No variant detected",
           ("no variant detected", "no pathogenic variant identified",
            "no pathogenic variant detected"), False),
        SV("PATHOGENIC", "Pathogenic variant detected",
           ("pathogenic variant detected", "likely pathogenic")),
        SV("VUS", "Variant of uncertain significance",
           ("variant of uncertain significance", "vus")),
        SV("BENIGN", "Benign variant", ("benign variant",)),
    ), M),
    "pcr_result": SC("pcr_result", "Assay result", (
        SV("NEGATIVE", "Not detected / negative",
           ("not detected", "negative"), False),
        SV("POSITIVE", "Detected / positive", ("detected", "positive")),
        SV("INDETERMINATE", "Indeterminate",
           ("indeterminate", "inconclusive"), False),
    ), M),
    "mutation_status": SC("mutation_status", "Mutation status", (
        SV("WILD_TYPE", "Wild type",
           ("wild type", "wild-type", "no egfr mutation", "no kras mutation",
            "mutation not detected"), False),
        SV("EGFR", "EGFR mutation detected", ("egfr mutation detected",)),
        SV("KRAS", "KRAS mutation detected", ("kras mutation detected",)),
        SV("BRAF", "BRAF V600E detected", ("braf v600e detected",)),
    ), M),
    "receptor_status": SC("receptor_status", "Receptor status", (
        SV("ER_POS", "ER positive", ("er positive",)),
        SV("ER_NEG", "ER negative", ("er negative",), False),
        SV("PR_POS", "PR positive", ("pr positive",)),
        SV("PR_NEG", "PR negative", ("pr negative",), False),
        SV("HER2_POS", "HER2 positive", ("her2 positive",)),
        SV("HER2_NEG", "HER2 negative", ("her2 negative",), False),
        SV("TRIPLE_NEG", "Triple negative", ("triple negative",), False),
    ), M),
    "msi_status": SC("msi_status", "Microsatellite status", (
        SV("MSI_HIGH", "MSI-high", ("msi-high", "mmr deficient")),
        SV("MSI_LOW", "MSI-low", ("msi-low",), False),
        SV("STABLE", "Microsatellite stable",
           ("microsatellite stable", "mmr proficient"), False),
    ), M),
}

CLAIM_TYPES = (
    ClaimTypeDef(
        key="MOLECULAR_TARGET_ABSENT",
        label="Molecular target reported absent",
        patterns=("no targetable mutation", "no actionable mutation",
                  "wild type", "wild-type", "mutation not detected"),
        requires_any=("variant_call", "mutation_status"),
        requires_labels=("A molecular / genetic report stating the call",),
        supportive_status_polarity=False,
        modality=M),
    ClaimTypeDef(
        key="VIRAL_SUPPRESSION",
        label="Viral suppression documented",
        patterns=("virally suppressed", "viral suppression",
                  "undetectable viral load", "viral load undetectable"),
        requires_any=("viral_load", "pcr_result"),
        requires_labels=("A quantitative viral load result",),
        supportive_direction=(("viral_load", "lt", 50.0),),
        supportive_status_polarity=False,
        modality=M),
    ClaimTypeDef(
        key="GENETIC_CAUSE_CONFIRMED",
        label="Genetic cause confirmed",
        patterns=("genetic cause confirmed", "genetically confirmed",
                  "diagnosis confirmed on genetic testing",
                  "pathogenic variant confirms"),
        requires_any=("variant_call",),
        requires_labels=("A genetic report reporting a pathogenic variant",),
        supportive_status_polarity=True,
        modality=M),
)

UNSUPPORTED_CONCEPT_LABELS = {
    "genetic_report": "Genetic / molecular report",
    "sequencing_report": "Sequencing report",
    "ihc_report": "Immunohistochemistry report",
    "flow_cytometry": "Flow cytometry report",
    "karyotype": "Karyotype report",
}

DOCUMENT_REFERENCE_PATTERNS = (
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(genetic|molecular|genomic)\s+(?:report|panel|testing)",
     "Genetic / molecular report", "PATHOLOGY_REPORT"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(?:ngs|sequencing)\s*(?:report|panel)?", "Sequencing report",
     "PATHOLOGY_REPORT"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(ihc|immunohistochemistry)\s*(?:report)?",
     "Immunohistochemistry report", "PATHOLOGY_REPORT"),
)

PACK = Pack(
    key="molecular", label="Molecular Pack", modality=M,
    concepts=CONCEPTS, claim_types=CLAIM_TYPES,
    unsupported_concept_labels=UNSUPPORTED_CONCEPT_LABELS,
    document_reference_patterns=DOCUMENT_REFERENCE_PATTERNS,
    # A molecular result is not re-run within days; a wider window is correct
    # for deciding two results describe the same episode.
    conflict_window_days={"viral_load": 30, "variant_allele_fraction": 90,
                          "tumor_mutational_burden": 180, "her2_ratio": 365},
    claim_lookback_days={"MOLECULAR_TARGET_ABSENT": 365,
                         "VIRAL_SUPPRESSION": 90,
                         "GENETIC_CAUSE_CONFIRMED": 3650},
    status_concepts=STATUS_CONCEPTS,
    document_cues=(
        ("MOLECULAR_REPORT", ("molecular diagnostics", "genomics",
                              "sequencing", "real-time pcr",
                              "cycle threshold", "variant", "assay :",
                              "assay:")),
    ),
    filename_cues=(("MOLECULAR_REPORT", ("molecular", "genomic", "ngs", "pcr")),),
    anchored_phrases=("detected", "not detected", "positive", "negative",
                      "indeterminate", "inconclusive"),
)
