# CARETRACE end-to-end implementation roadmap

The end-to-end architecture specification is the target engineering contract. CARETRACE must prove that clinical meaning survives ingestion, normalization, reconciliation, transformation, validation, and export; generating a target payload alone is not success.

## Implemented foundation

- Private case creation plus a durable, searchable patient directory.
- Stable external identifiers for bulk ingestion; uncertain or conflicting identities are not merged.
- One editable patient profile for both individual and bulk-created cases.
- Immutable original document storage and versioned text/OCR/layout extraction artifacts.
- Generic document classification across laboratory, imaging, cardiology, neurophysiology, molecular, consultation, discharge, and prescription records.
- Source-linked facts, claims, medications, events, document references, dates, units, coordinates, confidence, and raw text.
- Governed terminology acquisition and review-required terminology candidates.
- Versioned deterministic relationships, changes, conflicts, evidence gaps, timelines, briefs, and audit snapshots.
- Verified platform identity mapped to hospital organizations and exact-email memberships.
- Explicit OWNER, ADMIN, CLINICIAN, REVIEWER and VIEWER permissions enforced at the route layer.
- Tenant-scoped patient, document, bulk, terminology, transformation and audit queries with cross-tenant identifiers resolved as not found.
- Append-only actor events for patient access and mutation, source retrieval, bulk operations, processing, terminology administration and interoperability artifacts.
- Versioned FHIR R4 collections and controlled HL7 v2.5.1 ORU messages with checksum-addressed private artifacts, structural validation, responsible-agent provenance and field-level semantic-loss findings.
- Controlled FHIR/HL7 analysis that never creates or matches a patient automatically.

## Required foundation before hospital-wide production

- Durable job queue and event log for large asynchronous ingestion and transformation workloads.
- Human-review queues for identity, terminology, units, conflicts, and other high-risk ambiguity.
- Fine-grained patient assignment/consent policies beyond the implemented organization and role boundary.
- Retention, deletion, backup, environment-separation, and operational-observability controls.
- Clinical validation and formal security/compliance review. The current site remains a research prototype.

## Adapter and interoperability phases

1. Canonical JSON evidence export with a provenance manifest.
2. Extend the implemented controlled FHIR R4 collection into implementation-guide-aware ingestion, canonicalization and profile validation.
3. FHIR R5 and implementation-profile comparison.
4. Explicit, versioned mapping workbench and approval workflow.
5. Extend the implemented field-level semantic-loss report into approved equivalence rules and review workflows.
6. Extend the implemented HL7 v2.5.1 ORU/ZCT profile into negotiated site-specific mappings and interface-engine delivery.
7. DICOM metadata, CDA, and additional adapters driven by validated customer requirements.

Each phase must preserve the immutable source, represent uncertainty explicitly, use approved versioned mappings, validate the target, and retain enough metadata to reproduce the result.
