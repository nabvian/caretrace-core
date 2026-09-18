# Core integration

The deterministic Python core under `caretrace/` is the reference implementation
of the reconciliation rules. The deployed application does not run it — it does
not start that FastAPI server or load its synthetic PDFs. Instead the rules are
reimplemented on the tenant-safe TypeScript infrastructure and tested there. The
Python core stays around as a comparison point when a rule's behaviour is in
question.

## Where each rule lives

| Reference (Python) | Application (TypeScript) |
| --- | --- |
| Modality pack contract | `lib/evidence-packs.ts` — typed deterministic pack data |
| Unit-first quantitative extraction | `lib/document-extraction.ts` — generic label/value/unit extraction over text or OCR blocks |
| Imaging, ECG, EEG and molecular status values | Qualitative fact atoms with declared, mutually exclusive value classes |
| Episode-aware material conflicts | `lib/evidence-engine.ts` — single-link dated episodes, materiality thresholds, full member provenance |
| Claim lookback rules | Versioned claim rule bindings persisted with extracted claims |
| Patient registry and facts/claims views | React screens backed by tenant-scoped case and audit APIs |
| Patient profile and biomarker safety rules | Identity, source-linked observations, conflict members and date-safe change rules share the same audit objects rather than recomputing findings in the UI |
| Case codings screen | Local mappings, LOINC/RxNorm candidates and UCUM validation stay visibly advisory |
| Text-recognition screen | Health view for the private OCR service, model selection and immutable OCR policy |
| Offline source viewer | Immutable original, raw TXT, block/span and exact-source viewers |

## Infrastructure the application adds

- Authentication, hospital membership, RBAC and tenant isolation.
- D1 persistence, R2 immutable source/extraction artifacts and versioned audit snapshots.
- Single-patient and 10,000-report manifest bulk ingestion.
- The selective private OCR / layout service.
- FHIR R4, HL7 ORU and semantic-loss reporting.
- Official terminology acquisition and governed review candidates.

## Rules that must hold in both

- Report-layout coordinates are evidence, not report-specific parser templates.
- OCR and terminology candidates never overwrite source text.
- Same-episode disagreements stay unresolved; no source is chosen as correct.
- Later evidence does not retroactively support an earlier claim.
- A bulk manifest or an explicit case boundary owns patient assignment; OCR
  identity never silently merges or moves a record.

Reconciliation is deterministic. Accuracy comes from representative validation
data, terminology releases, review policy, and measured extraction performance —
not from the reconciliation step itself.
