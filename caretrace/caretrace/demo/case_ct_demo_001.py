"""CT-DEMO-001 — synthetic demonstration case.

ENTIRELY FICTIONAL. No real patient, clinician, facility, or record is
represented here. Names, identifiers, addresses and values were invented for
the purpose of exercising CARETRACE's audit engine.

The corpus is written as page-level document TEXT only. CARETRACE derives every
fact, claim, change, conflict and gap from this text by running the same
extraction and audit path that an uploaded PDF takes. Nothing in this module
tells the engine what the findings are.

Findings the text is designed to contain (for test assertions, not for display):
  1. Longitudinal change    Hb 9.2 (18 Jan) -> 10.4 (15 Mar) -> 8.7 (14 Jun)
  2. Numeric conflict       Hb 8.7 (CBC 14 Jun) vs 12.1 (Discharge 15 Jun)
  3. Duplicate value        MCV 68 fL restated in the June laboratory summary
  4. Medication conflict    ferrous sulfate active in Rx, absent from Jun list
  5. Unsupported claim      "iron deficiency confirmed" with no ferritin/TSAT
                            in the record on that date; ferritin arrives later
  6. Missing referenced doc discharge cites a CT report never uploaded
  7. Extraction-incomplete  referral letter carries no structured observations
  8. Second numeric conflict  Platelets 186 vs 402 on the same June episode
"""
from __future__ import annotations

CASE = {
    "case_ref": "CT-DEMO-001",
    "subject_label": "Arjun Mehta (synthetic)",
    "subject_dob": "1988-05-15",
    "is_synthetic": True,
    "notes": "Synthetic demonstration case. Fictional data only.",
}

_HDR = "MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)\n" \
       "12 Rowan Street, Fictionville  |  Lab Lic. SYN-0000\n" \
       "SYNTHETIC RECORD - NOT A REAL PATIENT REPORT\n"

_PT = "Patient: Arjun Mehta          Sex: M     DOB: 15 May 1988\n" \
      "Case Ref: CT-DEMO-001         MRN: SYN-448120\n"

_IMG = "NORTHFIELD IMAGING CENTRE (SYNTHETIC)\n" \
       "Radiology & Advanced Imaging  |  Reg. SYN-IMG-004\n" \
       "SYNTHETIC RECORD - NOT A REAL PATIENT REPORT\n"

_CARD = "ST. ANSELM CARDIAC SCIENCES (SYNTHETIC)\n" \
        "Non-Invasive Cardiology  |  Reg. SYN-CAR-017\n" \
        "SYNTHETIC RECORD - NOT A REAL PATIENT REPORT\n"

# Neurology and neurophysiology. The neurology note and the EEG previously
# carried the laboratory and cardiology letterheads respectively, which made
# the derived institution wrong for both -- an EEG is not a cardiology study.
_NEURO = "LAKESIDE NEUROSCIENCES INSTITUTE (SYNTHETIC)\n" \
         "Neurology & Clinical Neurophysiology  |  Reg. SYN-NEU-032\n" \
         "SYNTHETIC RECORD - NOT A REAL PATIENT REPORT\n"

_GEN = "HELIX GENOMICS (SYNTHETIC)\n" \
       "Molecular Diagnostics Division  |  CAP SYN-MOL-221\n" \
       "SYNTHETIC RECORD - NOT A REAL PATIENT REPORT\n"

# --------------------------------------------------------------------------
# Documents. Each entry: filename, declared type hint (for the PDF header
# only — classification is re-derived by the engine), doc date, and pages.
# --------------------------------------------------------------------------

DOCUMENTS: list[dict] = [

# 01 ------------------------------------------------------------------------
{
 "filename": "01_CBC_Jan.pdf",
 "title": "COMPLETE BLOOD COUNT",
 "doc_date": "2026-01-18",
 "pages": [
_HDR + _PT + """
Report Date: 18 January 2026            Sample: Whole blood (EDTA)
Requested by: Dr. R. Nair (synthetic)   Report No: LAB-26-00811

COMPLETE BLOOD COUNT
------------------------------------------------------------------
TEST                        RESULT      UNIT          REFERENCE
------------------------------------------------------------------
Hemoglobin                  9.2         g/dL          13.0 - 17.0
RBC Count                   4.42        x10^12/L      4.50 - 5.90
Hematocrit                 30.1         %             40.0 - 50.0
MCV                        68           fL            80 - 100
MCH                        20.8         pg            27.0 - 33.0
MCHC                       30.6         g/dL          32.0 - 36.0
RDW                        17.4         %             11.5 - 14.5
WBC Count                   6.8         x10^9/L       4.0 - 11.0
Platelet Count            349           x10^9/L       150 - 410
------------------------------------------------------------------

Comment: Microcytic hypochromic picture noted on the indices.
Peripheral smear examination advised.

Verified by: Dr. S. Kulkarni (synthetic), MD Pathology
"""]},

# 02 ------------------------------------------------------------------------
{
 "filename": "02_Prescription_Jan.pdf",
 "title": "PRESCRIPTION",
 "doc_date": "2026-01-20",
 "pages": [
"""RIVERSIDE INTERNAL MEDICINE CLINIC (SYNTHETIC)
Dr. R. Nair, MD  |  Reg. SYN-77120
SYNTHETIC RECORD - NOT A REAL PRESCRIPTION

""" + _PT + """
Date: 20 January 2026

Rx
------------------------------------------------------------------
1.  Ferrous sulfate 100 mg  --  once daily, oral
    Start date: 20 January 2026        Status: active
    Take after food. Continue for 12 weeks.

2.  Folic acid 5 mg  --  once daily, oral
    Start date: 20 January 2026        Status: active
------------------------------------------------------------------

Advice: Repeat CBC in 8 weeks.

Dr. R. Nair (synthetic)
"""]},

# 03 ------------------------------------------------------------------------
{
 "filename": "03_Consultation_Feb.pdf",
 "title": "CONSULTATION NOTE",
 "doc_date": "2026-02-09",
 "pages": [
"""RIVERSIDE INTERNAL MEDICINE CLINIC (SYNTHETIC)
Consultation Note  |  SYNTHETIC RECORD

""" + _PT + """
Consultation date: 09 February 2026
Seen by: Dr. R. Nair (synthetic)

History:
Three months of fatigue and reduced exercise tolerance. No overt bleeding
reported by the patient. Diet is predominantly vegetarian.

Examination:
Pallor of the conjunctivae. No organomegaly documented on examination.

Records reviewed:
CBC dated 18 January 2026 - Hemoglobin 9.2 g/dL, MCV 68 fL.

Assessment as documented:
Microcytic anaemia. Iron deficiency confirmed.
Thalassaemia trait excluded.

Plan:
Continue oral iron. Repeat CBC in 6 weeks.
"""]},

# 04 ------------------------------------------------------------------------
{
 "filename": "04_CBC_Mar.pdf",
 "title": "COMPLETE BLOOD COUNT",
 "doc_date": "2026-03-15",
 "pages": [
_HDR + _PT + """
Report Date: 15 March 2026              Sample: Whole blood (EDTA)
Requested by: Dr. R. Nair (synthetic)   Report No: LAB-26-04127

COMPLETE BLOOD COUNT
------------------------------------------------------------------
TEST                        RESULT      UNIT          REFERENCE
------------------------------------------------------------------
Hb                         10.4         g/dL          13.0 - 17.0
RBC Count                   4.61        x10^12/L      4.50 - 5.90
PCV                        33.8         %             40.0 - 50.0
MCV                        73           fL            80 - 100
MCH                        22.6         pg            27.0 - 33.0
MCHC                       30.8         g/dL          32.0 - 36.0
RDW                        16.1         %             11.5 - 14.5
TLC                         7.1         x10^9/L       4.0 - 11.0
PLT                       332           x10^9/L       150 - 410
------------------------------------------------------------------

Comment: Indices improved compared with the January report.

Verified by: Dr. S. Kulkarni (synthetic), MD Pathology
"""]},

# 05 ------------------------------------------------------------------------
{
 "filename": "05_Prescription_Mar.pdf",
 "title": "PRESCRIPTION",
 "doc_date": "2026-03-16",
 "pages": [
"""RIVERSIDE INTERNAL MEDICINE CLINIC (SYNTHETIC)
Dr. R. Nair, MD  |  Reg. SYN-77120
SYNTHETIC RECORD - NOT A REAL PRESCRIPTION

""" + _PT + """
Date: 16 March 2026

Rx
------------------------------------------------------------------
1.  Ferrous sulfate 100 mg  --  once daily, oral
    Status: active   (continued from 20 January 2026)

2.  Folic acid 5 mg  --  once daily, oral
    Status: active

3.  Vitamin C 500 mg  --  once daily, oral
    Status: active
------------------------------------------------------------------

Advice: Serum ferritin to be checked. Review with results.

Dr. R. Nair (synthetic)
"""]},

# 06 ------------------------------------------------------------------------
{
 "filename": "06_Ferritin_Report_Apr.pdf",
 "title": "IRON STUDIES - PARTIAL PANEL",
 "doc_date": "2026-04-12",
 "pages": [
_HDR + _PT + """
Report Date: 12 April 2026              Sample: Serum
Requested by: Dr. R. Nair (synthetic)   Report No: LAB-26-06550

IRON STUDIES (PARTIAL PANEL)
------------------------------------------------------------------
TEST                        RESULT      UNIT          REFERENCE
------------------------------------------------------------------
Serum Ferritin             18           ng/mL         30 - 400
------------------------------------------------------------------

Note: Transferrin saturation was not performed on this sample.
Serum iron and TIBC were not requested.

Verified by: Dr. S. Kulkarni (synthetic), MD Pathology
"""]},

# 07 ------------------------------------------------------------------------
{
 "filename": "07_CBC_Jun.pdf",
 "title": "COMPLETE BLOOD COUNT",
 "doc_date": "2026-06-14",
 "pages": [
_HDR + _PT + """
Report Date: 14 June 2026               Sample: Whole blood (EDTA)
Requested by: Dr. A. Fernandes (synthetic)  Report No: LAB-26-11902

COMPLETE BLOOD COUNT
------------------------------------------------------------------
TEST                        RESULT      UNIT          REFERENCE
------------------------------------------------------------------
Hemoglobin                  8.7         g/dL          13.0 - 17.0
RBC Count                   4.02        x10^12/L      4.50 - 5.90
Hematocrit                 28.4         %             40.0 - 50.0
MCV                        68           fL            80 - 100
MCH                        20.4         pg            27.0 - 33.0
MCHC                       30.2         g/dL          32.0 - 36.0
RDW                        18.2         %             11.5 - 14.5
WBC Count                   7.4         x10^9/L       4.0 - 11.0
Platelet Count            186           x10^9/L       150 - 410
Serum Creatinine            0.9         mg/dL         0.7 - 1.3
------------------------------------------------------------------

Comment: Microcytic hypochromic anaemia. Sample collected on admission.

Verified by: Dr. S. Kulkarni (synthetic), MD Pathology
"""]},

# 08 ------------------------------------------------------------------------
{
 "filename": "08_Discharge_Summary_Jun.pdf",
 "title": "DISCHARGE SUMMARY",
 "doc_date": "2026-06-15",
 "pages": [
"""NORTHFIELD GENERAL HOSPITAL (SYNTHETIC)
Department of Internal Medicine
SYNTHETIC RECORD - NOT A REAL DISCHARGE SUMMARY

""" + _PT + """
Admission date: 14 June 2026
Discharge date: 15 June 2026
Consultant: Dr. A. Fernandes (synthetic)
Discharge Summary  -  Page 1 of 3

Reason for admission:
Symptomatic anaemia with fatigue and exertional breathlessness.

Course in hospital:
Patient was admitted for evaluation of anaemia. Oral iron was reviewed
during the admission. Abdominal imaging was performed; CT findings as
described in the CT report.
""",
"""Discharge Summary  -  Page 2 of 3
Case Ref: CT-DEMO-001

Investigations during admission:
------------------------------------------------------------------
Serum Creatinine            0.9         mg/dL
Serum Ferritin              18          ng/mL   (dated 12 April 2026)
------------------------------------------------------------------

Assessment as documented at discharge:
Iron deficiency anaemia. Renal function normal.
GI blood loss excluded.
""",
"""Discharge Summary  -  Page 3 of 3
Case Ref: CT-DEMO-001

Laboratory summary at discharge:
------------------------------------------------------------------
Hemoglobin                 12.1         g/dL
Platelet Count            402           x10^9/L
------------------------------------------------------------------

Condition at discharge: stable. Haemoglobin normalised.

Discharge advice:
Repeat CBC in 4 weeks. Review in the outpatient clinic.

Dr. A. Fernandes (synthetic)
"""]},

# 09 ------------------------------------------------------------------------
{
 "filename": "09_Medication_List_Jun.pdf",
 "title": "MEDICATION LIST AT DISCHARGE",
 "doc_date": "2026-06-15",
 "pages": [
"""NORTHFIELD GENERAL HOSPITAL (SYNTHETIC)
Pharmacy - Medication List at Discharge
SYNTHETIC RECORD

""" + _PT + """
List date: 15 June 2026

CURRENT MEDICATIONS
------------------------------------------------------------------
DRUG                     DOSE      FREQUENCY      ROUTE   STATUS
------------------------------------------------------------------
Folic acid               5 mg      once daily     oral    active
Pantoprazole            40 mg      once daily     oral    active
Paracetamol            500 mg      as required    oral    active
------------------------------------------------------------------

This list reflects medications recorded at the time of discharge.

Pharmacist: M. Devi (synthetic)
"""]},

# 10 ------------------------------------------------------------------------
{
 "filename": "10_Referral_Letter.pdf",
 "title": "REFERRAL LETTER",
 "doc_date": "2026-06-20",
 # Rendered as a rasterised page with NO text layer, i.e. a scan. CARETRACE
 # ships no OCR engine, so this document must come out of ingestion as
 # extraction-incomplete rather than silently contributing nothing. The point
 # is that the failure is real and visible, not simulated with a flag.
 "scanned": True,
 "pages": [
"""RIVERSIDE INTERNAL MEDICINE CLINIC (SYNTHETIC)
SYNTHETIC RECORD - NOT A REAL REFERRAL

""" + _PT + """
Date: 20 June 2026

To: The Consultant Gastroenterologist
Northfield General Hospital (synthetic)

Dear Colleague,

Thank you for seeing this gentleman, who has been under review in this
clinic for anaemia over the past several months. He was recently admitted
and discharged from your institution.

I would be grateful for your assessment regarding further evaluation of
possible gastrointestinal blood loss. He remains on oral supplementation
and reports ongoing fatigue.

I have not enclosed the recent inpatient investigations; please refer to
the hospital record.

With thanks,

Dr. R. Nair (synthetic)
"""]},

# 11 ------------------------------------------------------------------------
{
 "filename": "11_Followup_Notes.pdf",
 "title": "FOLLOW-UP NOTE",
 "doc_date": "2026-07-06",
 "pages": [
"""RIVERSIDE INTERNAL MEDICINE CLINIC (SYNTHETIC)
Follow-up Note  |  SYNTHETIC RECORD

""" + _PT + """
Follow-up date: 06 July 2026
Seen by: Dr. R. Nair (synthetic)

Interval history:
Reviewed after the June admission. Reports persistent fatigue. States that
he stopped taking the iron tablets at some point during the admission but
is not certain of the date.

Records reviewed:
Discharge summary dated 15 June 2026.
CBC dated 14 June 2026 - Hemoglobin 8.7 g/dL.

Note: The discharge summary records a haemoglobin of 12.1 g/dL, which does
not match the CBC of 14 June 2026. Clarification has been requested from
the hospital.

Plan:
Repeat CBC. Restart oral iron pending review.
"""]},

# 12 ------------------------------------------------------------------------
{
 "filename": "12_Laboratory_Summary.pdf",
 "title": "CUMULATIVE LABORATORY SUMMARY",
 "doc_date": "2026-07-08",
 "pages": [
_HDR + _PT + """
Cumulative Laboratory Summary
Compiled: 08 July 2026                  Report No: LAB-26-13440

This summary restates previously reported results. It is a transcription of
earlier reports and does not represent new samples.

------------------------------------------------------------------
DATE            TEST                   RESULT      UNIT
------------------------------------------------------------------
18 Jan 2026     Hemoglobin              9.2        g/dL
18 Jan 2026     MCV                    68          fL
15 Mar 2026     Hemoglobin             10.4        g/dL
12 Apr 2026     Serum Ferritin         18          ng/mL
14 Jun 2026     Hemoglobin              8.7        g/dL
14 Jun 2026     MCV                    68          fL
------------------------------------------------------------------

Verified by: Dr. S. Kulkarni (synthetic), MD Pathology
"""]},
# 13 ------------------------------------------------------------------------
{
 "filename": "13_ECG_Report_Feb.pdf",
 "title": "ELECTROCARDIOGRAM REPORT",
 "doc_date": "2026-02-09",
 "pages": [
_CARD + _PT + """
Study Date: 09 February 2026             Study No: ECG-26-0417
Referred by: Dr. A. Sharma (synthetic)   Modality: 12-lead ECG

MEASUREMENTS
  Ventricular rate .......... 96 bpm
  PR interval ............... 148 ms
  QRS duration .............. 88 ms
  QT interval ............... 386 ms
  QTc (Bazett) .............. 428 ms

INTERPRETATION
Sinus rhythm. No acute ST-T changes. No conduction block.
Borderline sinus tachycardia at the time of recording.

Reported by: Dr. P. Iyer (synthetic), DM Cardiology
"""]},

# 14 ------------------------------------------------------------------------
{
 "filename": "14_Chest_Xray_Mar.pdf",
 "title": "CHEST RADIOGRAPH REPORT",
 "doc_date": "2026-03-15",
 "pages": [
_IMG + _PT + """
Examination Date : 15 March 2026
Accession        : IMG-26-2201
Modality         : Digital radiography, chest PA
Referring Doctor : Dr. A. Sharma (synthetic)

FINDINGS
Lung fields are clear. No consolidation. No pleural effusion.
Cardiac silhouette within normal limits. Bony cage intact; no fracture.

IMPRESSION
Study is unremarkable.

Reported by : Dr. M. D'Souza (synthetic), MD Radiodiagnosis
Technologist : Mr. K. Verma (synthetic)
"""]},

# 15 ------------------------------------------------------------------------
{
 "filename": "15_CT_Abdomen_Apr.pdf",
 "title": "CT ABDOMEN REPORT",
 "doc_date": "2026-04-20",
 "pages": [
_IMG + _PT + """
Examination Date : 20 April 2026
Accession        : IMG-26-2588
Modality         : CT abdomen and pelvis, portal venous phase
Indication       : Anaemia under evaluation. Assess for occult source.

FINDINGS
Liver span 14.2 cm; parenchyma homogeneous.
Spleen 11.4 cm, normal in echotexture.
Right kidney length 10.8 cm. Left kidney length 10.6 cm.
A 9 mm hypodense lesion is noted in segment VI of the liver.
No metastasis. No free fluid.

IMPRESSION
Small hepatic lesion, likely benign on this appearance.
Interval imaging in 6 months suggested.

Reported by : Dr. M. D'Souza (synthetic), MD Radiodiagnosis
"""]},

# 16 ------------------------------------------------------------------------
{
 "filename": "16_MRI_Brain_Jun.pdf",
 "title": "MRI BRAIN REPORT",
 "doc_date": "2026-06-16",
 "pages": [
_IMG + _PT + """
Examination Date : 16 June 2026
Accession        : IMG-26-3120
Modality         : MRI brain, plain
Indication       : Transient giddiness during admission.

FINDINGS
Diffusion-weighted imaging shows no restricted diffusion.
No acute infarct. No intracranial bleed.
Ventricles and sulci are age appropriate.

IMPRESSION
No acute intracranial abnormality.

Reported by : Dr. M. D'Souza (synthetic), MD Radiodiagnosis
"""]},

# 17 ------------------------------------------------------------------------
{
 "filename": "17_Neurology_Note_Jun.pdf",
 "title": "NEUROLOGY CONSULTATION NOTE",
 "doc_date": "2026-06-17",
 "pages": [
_NEURO + _PT + """
Consultation Date: 17 June 2026          Unit: Neurology
Seen by: Dr. V. Rao (synthetic), DM Neurology

History:
Reviewed during the current admission for symptomatic anaemia.
Transient giddiness reported on 15 June 2026.

Assessment:
MRI brain reviewed. Acute infarct noted in the right parietal region.
Advise antiplatelet therapy and neurology follow-up.

Plan:
EEG to be obtained. Repeat MRI in 3 months.
"""]},

# 18 ------------------------------------------------------------------------
{
 "filename": "18_EEG_Report_Jun.pdf",
 "title": "ELECTROENCEPHALOGRAM REPORT",
 "doc_date": "2026-06-19",
 "pages": [
_NEURO + _PT + """
Study Date: 19 June 2026                 Study No: EEG-26-0088
Referred by: Dr. V. Rao (synthetic)      Montage: 10-20 international

TECHNICAL
Recording duration 32 minutes. Awake and drowsy states sampled.

FINDINGS
Posterior dominant rhythm 9.5 Hz, symmetric and reactive.
No epileptiform discharges. No asymmetry. No electrographic seizures.

IMPRESSION
Normal EEG.

Reported by: Dr. V. Rao (synthetic), DM Neurology
Technologist: Ms. L. Pinto (synthetic)
"""]},

# 19 ------------------------------------------------------------------------
{
 "filename": "19_Molecular_Report_Jul.pdf",
 "title": "MOLECULAR DIAGNOSTICS REPORT",
 "doc_date": "2026-07-02",
 "pages": [
_GEN + _PT + """
Collection Date : 28 June 2026        Report Date : 02 July 2026
Accession       : MOL-26-0774         Specimen    : Peripheral blood
Ordered by      : Dr. R. Nair (synthetic)

ASSAY : Targeted haemoglobinopathy panel (HBB, HBA1, HBA2)
        Quantitative HBV DNA by real-time PCR

RESULT SUMMARY
  Analyte                          Result            Unit
  HBB sequencing                   No pathogenic variant detected
  Alpha-globin deletion            Not detected
  HBV DNA                          Not detected      copies/mL
  Cycle threshold (Ct)             38.4

INTERPRETATION
No pathogenic variant identified in the genes examined.
Haemoglobinopathy not supported by this panel.

Reported by : Dr. N. Kapoor (synthetic), PhD FACMG
"""]},

]


def document_texts() -> list[dict]:
    """Return the corpus as [{filename, title, doc_date, pages:[str]}]."""
    return [dict(d) for d in DOCUMENTS]
