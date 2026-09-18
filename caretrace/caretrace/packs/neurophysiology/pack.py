"""Neurophysiology Pack — EEG, EMG, nerve conduction studies.

EEG reports state background frequency numerically and epileptiform activity as
a presence/absence finding. Nerve conduction studies report velocities and
latencies.
"""
from __future__ import annotations

from ..base import (ClaimTypeDef, ConceptDef, Pack,
                    StatusConceptDef as SC, StatusValue as SV)

M = "NEUROPHYSIOLOGY"

CONCEPTS = {
    "eeg_background_freq": ConceptDef(
        "eeg_background_freq", "EEG background frequency", "Hz", 1.0, 0.15,
        ("background frequency", "posterior dominant rhythm", "pdr",
         "background rhythm", "alpha frequency"),
        (("hz", "Hz"), ("cps", "Hz")), M),
    "nerve_conduction_velocity": ConceptDef(
        "nerve_conduction_velocity", "Nerve conduction velocity", "m/s", 5.0, 0.12,
        ("conduction velocity", "ncv", "nerve conduction velocity",
         "motor conduction velocity", "sensory conduction velocity"),
        (("m/sec", "m/s"), ("meters/second", "m/s")), M),
    "distal_latency": ConceptDef(
        "distal_latency", "Distal motor latency", "ms", 0.8, 0.15,
        ("distal latency", "distal motor latency", "terminal latency"),
        (("msec", "ms"), ("s", "ms")), M),
    "f_wave_latency": ConceptDef(
        "f_wave_latency", "F-wave latency", "ms", 2.0, 0.12,
        ("f wave latency", "f-wave latency", "f wave"), (("msec", "ms"),), M),
    "cmap_amplitude": ConceptDef(
        "cmap_amplitude", "CMAP amplitude", "mV", 1.0, 0.20,
        ("cmap", "cmap amplitude", "compound motor action potential"),
        (("millivolt", "mV"),), M),
}

STATUS_CONCEPTS = {
    "epileptiform_activity": SC("epileptiform_activity", "Epileptiform activity", (
        SV("ABSENT", "No epileptiform activity",
           ("no epileptiform activity", "no epileptiform discharges",
            "no epileptiform abnormality"), False),
        SV("PRESENT", "Epileptiform discharges present",
           ("epileptiform discharges", "spike and wave", "sharp waves",
            "epileptiform activity")),
    ), M),
    "seizure_activity": SC("seizure_activity", "Electrographic seizure activity", (
        SV("ABSENT", "No seizure activity",
           ("no seizure activity", "no electrographic seizures"), False),
        SV("PRESENT", "Electrographic seizure recorded",
           ("electrographic seizure",)),
    ), M),
    "eeg_asymmetry": SC("eeg_asymmetry", "EEG focality", (
        SV("NORMAL", "No focal abnormality",
           ("no asymmetry", "no focal abnormality"), False),
        SV("FOCAL", "Focal slowing", ("focal slowing",)),
        SV("GENERALISED", "Generalised slowing",
           ("generalised slowing", "generalized slowing")),
    ), M),
    "demyelination": SC("demyelination", "Nerve conduction pattern", (
        SV("ABSENT", "No demyelinating features",
           ("no demyelinating features", "no features of demyelination"), False),
        SV("DEMYELINATING", "Demyelinating pattern",
           ("demyelinating pattern", "features of demyelination")),
        SV("AXONAL", "Axonal pattern", ("axonal pattern",)),
    ), M),
}

CLAIM_TYPES = (
    ClaimTypeDef(
        key="EEG_NORMAL",
        label="EEG reported normal",
        patterns=("eeg is normal", "normal eeg", "eeg within normal limits",
                  "electroencephalogram normal"),
        requires_any=("eeg_background_freq", "epileptiform_activity"),
        requires_labels=("An EEG report stating background and epileptiform activity",),
        supportive_status_polarity=False,
        modality=M),
    ClaimTypeDef(
        key="NEUROPATHY_PRESENT",
        label="Peripheral neuropathy documented",
        patterns=("peripheral neuropathy", "polyneuropathy",
                  "neuropathy confirmed", "evidence of neuropathy"),
        requires_any=("nerve_conduction_velocity", "distal_latency", "demyelination"),
        requires_labels=("Nerve conduction study report",),
        supportive_direction=(("nerve_conduction_velocity", "lt", 40.0),),
        supportive_status_polarity=True,
        modality=M),
)

UNSUPPORTED_CONCEPT_LABELS = {
    "eeg_report": "EEG report",
    "emg_report": "EMG report",
    "ncs_report": "Nerve conduction study report",
}

DOCUMENT_REFERENCE_PATTERNS = (
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(eeg|electroencephalogram)\s*(?:report)?", "EEG report", "OTHER"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(emg|electromyogra\w+)\s*(?:report)?", "EMG report", "OTHER"),
    (r"\b(?:as (?:described|reported) (?:in|on)|see|refer to|per)\s+"
     r"(?:the\s+)?(?:ncs|nerve conduction)\s*(?:study|report)?",
     "Nerve conduction study report", "OTHER"),
)

PACK = Pack(
    key="neurophysiology", label="Neurophysiology Pack", modality=M,
    concepts=CONCEPTS, claim_types=CLAIM_TYPES,
    unsupported_concept_labels=UNSUPPORTED_CONCEPT_LABELS,
    document_reference_patterns=DOCUMENT_REFERENCE_PATTERNS,
    conflict_window_days={"eeg_background_freq": 7,
                          "nerve_conduction_velocity": 30},
    claim_lookback_days={"EEG_NORMAL": 180, "NEUROPATHY_PRESENT": 365},
    status_concepts=STATUS_CONCEPTS,
    document_cues=(
        ("EEG_REPORT", ("electroencephalogram", "eeg report",
                        "posterior dominant rhythm", "10-20 international",
                        "epileptiform")),
    ),
    filename_cues=(("EEG_REPORT", ("eeg", "emg", "ncs")),),
)
