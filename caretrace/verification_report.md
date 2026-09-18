# CARETRACE — verification report

Every row below is a predicate evaluated against live output from the deterministic engine on case `CT-DEMO-001`, not a hand-written claim. Regenerate with `python verify.py`.

**Result: 22/22 acceptance checks pass. 16-stage pipeline, 240 unit tests passing.**

## Computed audit metrics

| Metric | Value |
| --- | --- |
| Processed | yes |
| Documents | 19 |
| Pages | 21 |
| Facts | 68 |
| Claims | 12 |
| Medications | 8 |
| Changes | 18 |
| Conflicts | 5 |
| Evidence gaps | 6 |
| Relationships | 92 |
| Unresolved | 5 |
| Source traceability | 100% |
| Documents incomplete | 1 |
| Codings | 8 |
| Patients | 1 |
| Identity review | 1 |

## Acceptance criteria

| Section | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| Upload | Upload PDF/image documents | PASS | 19 documents ingested |
|  | Document list with metadata | PASS | 11 distinct document types, 21 pages |
| Processing | Process a case end-to-end | PASS | 16 of 16 declared pipeline stages ran |
|  | Terminology runs after the audit | PASS | RESOLVE_TERMINOLOGY follows GENERATE_AUDIT |
|  | Generate structured facts | PASS | 68 facts |
|  | Generate claims | PASS | 12 claims |
|  | Generate events / medications | PASS | 8 medications |
|  | Generate relationships | PASS | 92 relationships |
| Audit | Detect documented changes | PASS | 18 changes |
|  | Detect numeric conflicts | PASS | 2 numeric conflicts |
|  | Detect medication conflicts | PASS | 2 medication conflicts |
|  | Detect unsupported claims | PASS | 3 claims with no located evidence |
|  | Detect missing referenced documents | PASS | 1 referenced documents not uploaded |
|  | Preserve provenance on every finding | PASS | source traceability 100% |
|  | Audit is identical with every vocabulary offline | PASS | 15 metrics byte-identical offline; codings 8 -> 0 |
|  | Never auto-resolve a conflict | PASS | all 5 conflicts UNRESOLVED |
| Output | Timeline with source links | PASS | 94 entries across 14 dates, all with provenance |
| Registry | Documents resolved to a patient record | PASS | 18 of 19 documents linked to 1 patient record(s) |
|  | Weak or ambiguous identity is queued, never merged | PASS | 1 document(s) awaiting review, each with a stated basis and rationale |
|  | Every resolved link records how it was matched | PASS | each linked document carries the matching rule that placed it |
|  | Care team attributed without inventing affiliations | PASS | 8 clinicians, one row each; affiliation only where a document implies it |
| Output | Evidence brief | PASS | rendered at #/brief, print/PDF via browser |

## Pipeline stages

INGEST → CLASSIFY → EXTRACT → NORMALIZE → CREATE_FACTS → CREATE_CLAIMS → CREATE_EVENTS → BUILD_REGISTRY → RESOLVE_ENTITIES → DETECT_CHANGES → DETECT_CONFLICTS → RESOLVE_CLAIMS → BUILD_RELATIONSHIPS → DETECT_GAPS → GENERATE_AUDIT → RESOLVE_TERMINOLOGY

## The findings the engine produced

### Conflicts (never auto-resolved)

- **CF-001 · Hemoglobin** — 8.7 g/dL (11_Followup_Notes.pdf p1, 12_Laboratory_Summary.pdf p1, 07_CBC_Jun.pdf p1) vs 12.1 g/dL (08_Discharge_Summary_Jun.pdf p3, 11_Followup_Notes.pdf p1). Status: UNRESOLVED.
- **CF-002 · Platelet Count** — 186 x10^9/L (07_CBC_Jun.pdf p1) vs 402 x10^9/L (08_Discharge_Summary_Jun.pdf p3). Status: UNRESOLVED.
- **CF-003 · Acute infarct** — No acute infarct (16_MRI_Brain_Jun.pdf p1) vs Acute infarct present (17_Neurology_Note_Jun.pdf p1). Status: UNRESOLVED.
- **CF-004 · Vitamin C 500.0mg** — Vitamin C — documented active (2026-03-16) in 05_Prescription_Mar.pdf p1; Vitamin C — not listed on 09_Medication_List_Jun.pdf. Status: UNRESOLVED.
- **CF-005 · Ferrous sulfate 100.0mg** — Ferrous sulfate — documented active (2026-01-20, 2026-03-16) in 02_Prescription_Jan.pdf p1, 05_Prescription_Mar.pdf p1; Ferrous sulfate — not listed on 09_Medication_List_Jun.pdf. Status: UNRESOLVED.

### Evidence gaps

- **G-001 · Microcytic anaemia. Iron deficiency confirmed** (MISSING_SUPPORTING_TEST) — not located: Serum Ferritin, Transferrin saturation (TSAT), Serum iron.
- **G-002 · Thalassaemia trait excluded** (MISSING_SUPPORTING_TEST) — not located: Hemoglobin electrophoresis, HPLC.
- **G-003 · GI blood loss excluded** (MISSING_SUPPORTING_TEST) — not located: Faecal occult blood test, Endoscopy report.
- **G-004 · CT report** (MISSING_SOURCE) — not located: CT report.
- **G-005 · Vitamin C** (MEDICATION_DOCUMENTATION_GAP) — not located: Entry on the later medication list, A documented stop date or discontinuation note.
- **G-006 · Ferrous sulfate** (MEDICATION_DOCUMENTATION_GAP) — not located: Entry on the later medication list, A documented stop date or discontinuation note.

### Terminology (advisory layer)

Vocabulary codings link a document's wording to a published concept. They are advisory: the audit above is computed from CARETRACE's own packs and does not read them.

| Vocabulary | State | Codes | Release |
| --- | --- | --- | --- |
| RxNorm (NLM RxNav) | ACTIVE | medication | 03-Aug-2026 |
| LOINC (Regenstrief FHIR server) | UNLICENSED | observation | not reported |
| SNOMED CT (Snowstorm) | UNLICENSED | finding, observation | not reported |
| ICD-11 (WHO ICD API) | UNLICENSED | diagnosis_statement | not reported |

With every provider unreachable the audit is unchanged — 15 of 15 audit metrics identical, codings 8 -> 0. An approximate match is never asserted: a coding carries its match kind and only exact or synonym matches are marked assertable.

### Notable engine behaviours

- **Evidence dated after a claim does not support it.** The iron-deficiency claim is dated 2026-02-09; the only ferritin result in the records is 2026-04-12. The engine reports the claim as having no located evidence *and* discloses why the later result does not count, so a reviewer who has seen that ferritin value elsewhere does not read the gap as an extraction miss:

  > The active pack declares evidence for this claim type. No qualifying observation was located in the uploaded records within 180 days before the claim date. This is a statement about the records, not about the claim. Serum Ferritin is documented in the records (18 ng/mL on 2026-04-12) but is dated after this claim, so it cannot be evidence the claim was based on.
- **Conflicts are reported across all restatements.** CF-001 draws on 4 documents (3 record(s) carrying one value, 2 the other); every source is listed rather than collapsed to a representative pair. One document — 11_Followup_Notes.pdf — appears on both sides, because it restates both values; the conflict is between the values, not between documents.
- **One document yielded no structured facts.** `10_Referral_Letter.pdf` is marked EXTRACTION_INCOMPLETE and reported as requiring review rather than silently dropped; it appears as an isolated node in the evidence graph.
- **Absence is never phrased as falsehood.** Gap language is "evidence not located", a statement about the records; conflicts stay UNRESOLVED with both sources preserved.

## Scope

Research/prototype software. Not a diagnostic or treatment system, and not clinically validated. All patient data is synthetic.
