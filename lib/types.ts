export type DocumentType =
  | "LAB_REPORT"
  | "PRESCRIPTION"
  | "CONSULTATION"
  | "DISCHARGE_SUMMARY"
  | "MEDICATION_LIST"
  | "REFERRAL"
  | "FOLLOWUP"
  | "IMAGING_REPORT"
  | "CARDIOLOGY_REPORT"
  | "NEUROPHYSIOLOGY_REPORT"
  | "MOLECULAR_REPORT"
  | "PATHOLOGY_REPORT"
  | "OTHER";

export type FindingStatus =
  | "VERIFIED"
  | "DOCUMENTED"
  | "CHANGED"
  | "CONFLICT"
  | "MISSING"
  | "UNRESOLVED";

export type CaseLifecycleState =
  | "EMPTY"
  | "EXTRACTED"
  | "AUDIT_REQUIRED"
  | "AUDITING"
  | "AUDITED"
  | "REVIEW_REQUIRED"
  | "FAILED";

export interface CaseRecord {
  id: string;
  caseCode: string;
  patientName: string;
  dob: string | null;
  address: string | null;
  contactNumber: string | null;
  email: string | null;
  lifecycleState: CaseLifecycleState;
  lifecycleUpdatedAt: string;
  synthetic: boolean;
  createdAt: string;
}

export interface MedicalDocument {
  id: string;
  name: string;
  type: DocumentType;
  mediaType?: string;
  date: string;
  pages: number;
  uploadStatus: "UPLOADED" | "DEMO";
  processingStatus: "READY" | "PROCESSED" | "REQUIRES_REVIEW";
  pageText: Record<number, string>;
  processingNote?: string;
  uploadedAt?: string;
  clinicalDates?: ClinicalDate[];
  extraction?: { method: ExtractionMethod; engine: string; model: string; modelVersion: string; status: "COMPLETE" | "REQUIRES_REVIEW" | "FAILED"; confidence: number | null; createdAt: string };
  metadataCandidates?: ReportMetadataCandidate[];
}

export type ClinicalDateType = "specimen_collection" | "report" | "encounter" | "admission" | "discharge" | "procedure" | "medication_start" | "medication_stop" | "follow_up" | "document";
export interface ClinicalDate { value: string; type: ClinicalDateType; precision: "day" | "month" | "year"; sourcePage: number; sourceText: string; confidence: "explicit"; }

export type ExtractionMethod = "PDF_TEXT_LAYER" | "PADDLE_OCR" | "PADDLE_OCR_VL" | "PP_STRUCTURE_V3" | "HYBRID";

export interface ExtractionBlock {
  id: string;
  pageNumber: number;
  text: string;
  confidence: number;
  bbox: [number, number, number, number] | null;
  kind: "TEXT" | "TABLE" | "FORM" | "OTHER";
  readingOrder: number;
}

export interface RawExtractionPage {
  pageNumber: number;
  text: string;
  confidence: number;
  width: number | null;
  height: number | null;
  method: Exclude<ExtractionMethod, "HYBRID">;
  blocks: ExtractionBlock[];
}

export interface RawExtractionArtifact {
  id: string;
  schemaVersion: "caretrace.raw-extraction.v1";
  sourceSha256: string;
  createdAt: string;
  status: "COMPLETE" | "REQUIRES_REVIEW" | "FAILED";
  method: ExtractionMethod;
  engine: string;
  model: string;
  modelVersion: string;
  pages: RawExtractionPage[];
  attempts: Array<{ method: ExtractionMethod; engine: string; model: string; modelVersion: string; status: "COMPLETE" | "FAILED"; note?: string; pages?: RawExtractionPage[] }>;
  warnings: string[];
}

export type ReportMetadataField = "patient_name" | "patient_identifier" | "report_date" | "institution" | "suggested_by" | "reporting_clinician" | "technician";
export interface SourceProvenance { extractionId: string; blockIds: string[]; bbox: [number, number, number, number] | null; confidence: number; method: ExtractionMethod; engine: string; model: string; modelVersion: string; }
export interface EvidenceSourceSpan extends SourceProvenance {
  id: string;
  documentId: string;
  pageNumber: number;
  sourceText: string;
  charStart: number | null;
  charEnd: number | null;
  role: "PRIMARY" | "SUPPORTING" | "TEMPORAL" | "QUALIFIER";
  ordinal: number;
}
export interface ReportMetadataCandidate { id: string; field: ReportMetadataField; value: string; sourcePage: number; sourceText: string; confidence: number; status: "DOCUMENTED" | "REVIEW_REQUIRED"; sourceProvenance: SourceProvenance; }

export interface Fact {
  id: string;
  displayId: string;
  concept: string;
  originalConcept: string;
  value: number | string;
  unit: string | null;
  date: string | null;
  datePrecision: "day" | "month" | "year" | "unknown";
  sourceDocumentId: string;
  sourceDocument: string;
  sourcePage: number;
  sourceText: string;
  confidence: number;
  type: "OBSERVATION";
  modality?: "LABORATORY" | "IMAGING" | "CARDIOLOGY" | "NEUROPHYSIOLOGY" | "MOLECULAR" | "OTHER";
  valueKey?: string;
  reviewStatus?: "DOCUMENTED" | "REVIEW_REQUIRED";
  sourceProvenance?: SourceProvenance;
  sourceSpans?: EvidenceSourceSpan[];
  terminology: { caretraceId: string; sourceText: string; matchType: "EXACT" | "ALIAS" | "NORMALIZED"; terminologySource: string; sourceCode: string; sourceVersion: string; sourceUri: string; checksumVerified: boolean | null };
  standardCandidates?: Array<{ sourceSystem: "loinc"; sourceCode: string; sourceVersion: string; sourceUri: string; label: string; status: "REVIEW_REQUIRED"; unitCompatible: boolean | null; reason: string }>;
  unitValidation?: { system: "ucum"; status: "VALID" | "INVALID" | "NO_ACTIVE_RELEASE"; valid: boolean | null; sourceVersion: string | null; sourceUri: string; reason: string };
  temporal: { eventDate: string | null; dateType: ClinicalDateType | null; precision: "day" | "month" | "year" | null; status: "EXPLICIT" | "NOT_FOUND" | "AMBIGUOUS"; sourcePage: number | null; sourceText: string | null; confidence: "explicit" | null };
  observation?: { referenceRange: { low: number | null; high: number | null; text: string } | null; specimen: string | null; unitStatus: "VALID" | "NOT_DOCUMENTED"; extractionMethod: ExtractionMethod | "SYNTHETIC"; rawValue?: string; rawUnit?: string | null; conversionFactor?: number | null };
}

export interface Medication {
  id: string;
  displayId: string;
  drugName: string;
  normalizedDrug: string;
  ingredient: string | null;
  brand: string | null;
  strength: string | null;
  strengthUnit: string | null;
  dose: string | null;
  doseAmount: string | null;
  doseUnit: string | null;
  doseForm: string | null;
  frequency: string | null;
  route: string | null;
  duration: string | null;
  status: "ACTIVE" | "INACTIVE" | "NOT_LISTED";
  date: string | null;
  startDate: string | null;
  stopDate: string | null;
  prescriber: string | null;
  sourceDocumentId: string;
  sourceDocument: string;
  sourcePage: number;
  sourceText: string;
  confidence: number;
  reviewStatus?: "DOCUMENTED" | "REVIEW_REQUIRED";
  sourceProvenance?: SourceProvenance;
  sourceSpans?: EvidenceSourceSpan[];
  standardCandidates?: Array<{ sourceSystem:"rxnorm";sourceCode:string;sourceVersion:string;sourceUri:string;label:string;semanticType:string;status:"REVIEW_REQUIRED";reason:string }>;
}

export interface Claim {
  id: string;
  displayId: string;
  claim: string;
  date: string | null;
  sourceDocumentId: string;
  sourceDocument: string;
  sourcePage: number;
  sourceText: string;
  confidence: number;
  category?: "FINDING" | "IMPRESSION" | "CONCLUSION" | "INTERPRETATION" | "RESULT" | "DOCUMENTED_DIAGNOSIS";
  reviewStatus?: "DOCUMENTED" | "REVIEW_REQUIRED";
  sourceProvenance?: SourceProvenance;
  sourceSpans?: EvidenceSourceSpan[];
  supportConcepts?: string[];
  gapRule?: "MISSING_SUPPORT" | "MISSING_SOURCE" | "MISSING_FOLLOWUP";
  referencedDocument?: string;
  expectedConcept?: string;
  claimType?: string;
  evidenceLookbackDays?: number;
  evidenceLabels?: string[];
}

export interface DocumentReference {
  id: string;
  displayId: string;
  label: string;
  targetDocumentType: DocumentType | null;
  referencedDate: string | null;
  resolvedDocumentId: string | null;
  status: "RESOLVED" | "NOT_PRESENT" | "REVIEW_REQUIRED";
  sourceDocumentId: string;
  sourceDocument: string;
  sourcePage: number;
  sourceText: string;
  confidence: number;
  reviewStatus: "DOCUMENTED" | "REVIEW_REQUIRED";
  sourceProvenance?: SourceProvenance;
  sourceSpans?: EvidenceSourceSpan[];
}

export interface MedicalEvent {
  id: string;
  displayId: string;
  eventType: ClinicalDateType;
  label: string;
  date: string;
  datePrecision: "day" | "month" | "year";
  sourceDocumentId: string;
  sourceDocument: string;
  sourcePage: number;
  sourceText: string;
  confidence: number;
  reviewStatus: "DOCUMENTED" | "REVIEW_REQUIRED";
  sourceProvenance?: SourceProvenance;
  sourceSpans?: EvidenceSourceSpan[];
}

export interface Relationship {
  id: string;
  fromId: string;
  toId: string;
  type:
    | "SUPPORTS"
    | "CONTRADICTS"
    | "MENTIONS"
    | "DUPLICATES"
    | "SUPERSEDES"
    | "PRECEDES"
    | "FOLLOWS"
    | "SAME_CONCEPT"
    | "CHANGED_FROM"
    | "CHANGED_TO"
    | "MISSING_SUPPORT";
  rationale: string;
}

export interface ChangeEvent {
  id: string;
  concept: string;
  from: Fact;
  to: Fact;
  label: "Documented change";
}

export interface Conflict {
  id: string;
  displayId: string;
  kind: "NUMERIC" | "STATUS" | "MEDICATION";
  concept: string;
  date: string;
  status: "UNRESOLVED";
  evidenceA: Fact | Medication;
  evidenceB: Fact | Medication;
  evidenceAMembers?: Array<Fact | Medication>;
  evidenceBMembers?: Array<Fact | Medication>;
  episodeStart?: string;
  episodeEnd?: string;
  materialityBasis?: string;
  explanation: string;
}

export interface EvidenceGap {
  id: string;
  displayId: string;
  kind: "MISSING_SUPPORTING_TEST" | "MISSING_REFERENCED_DOCUMENT" | "MISSING_FOLLOWUP";
  title: string;
  claim: Claim;
  reference?: DocumentReference;
  evidenceLocated: string[];
  evidenceNotLocated: string[];
  basis?: string;
  laterEvidence?: string[];
  status: "SUPPORTING_EVIDENCE_NOT_FOUND" | "NOT_PRESENT_IN_RECORDS" | "FOLLOWUP_NOT_LOCATED";
}

export interface TimelineEvent {
  id: string;
  date: string | null;
  title: string;
  document: MedicalDocument;
  detail: string;
  factIds: string[];
  flags: string[];
}

export interface AuditResult {
  run?: { id: string; sequence: number; rulesetVersion: string; status: "COMPLETED" | "REQUIRES_REVIEW"; startedAt: string; completedAt: string; sourceSnapshotSha256: string };
  caseRecord: CaseRecord;
  documents: MedicalDocument[];
  facts: Fact[];
  claims: Claim[];
  medications: Medication[];
  events: MedicalEvent[];
  documentReferences: DocumentReference[];
  changes: ChangeEvent[];
  conflicts: Conflict[];
  gaps: EvidenceGap[];
  relationships: Relationship[];
  timeline: TimelineEvent[];
  metrics: {
    documents: number;
    facts: number;
    claims: number;
    medications: number;
    events: number;
    references: number;
    changes: number;
    conflicts: number;
    gaps: number;
    unresolved: number;
    traceability: number;
  };
}
