import { index, integer, real, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

const timestamps = {
  createdAt: text("created_at").notNull(),
  updatedAt: text("updated_at").notNull(),
};

export const hospitalOrganizations = sqliteTable("hospital_organizations", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  ...timestamps,
});
export const hospitalBootstrap = sqliteTable("hospital_bootstrap", {
  id: text("id").primaryKey(),
  organizationId: text("organization_id").notNull().references(() => hospitalOrganizations.id, { onDelete: "restrict" }),
  ownerUserId: text("owner_user_id").notNull(),
  createdAt: text("created_at").notNull(),
});
export const hospitalMemberships = sqliteTable("hospital_memberships", {
  id: text("id").primaryKey(),
  organizationId: text("organization_id").notNull().references(() => hospitalOrganizations.id, { onDelete: "cascade" }),
  userId: text("user_id"),
  email: text("email").notNull(),
  displayName: text("display_name"),
  role: text("role").notNull(),
  status: text("status").notNull(),
  invitedByUserId: text("invited_by_user_id"),
  createdAt: text("created_at").notNull(),
  claimedAt: text("claimed_at"),
  updatedAt: text("updated_at").notNull(),
}, (table) => [
  uniqueIndex("idx_hospital_memberships_org_email").on(table.organizationId, table.email),
  uniqueIndex("idx_hospital_memberships_org_user").on(table.organizationId, table.userId),
  index("idx_hospital_memberships_user").on(table.userId, table.status, table.organizationId),
  index("idx_hospital_memberships_invite").on(table.email, table.status, table.organizationId),
]);

export const cases = sqliteTable("cases", {
  id: text("id").primaryKey(),
  caseCode: text("case_code").notNull().unique(),
  patientLabel: text("patient_label").notNull(),
  dob: text("dob"),
  address: text("address"),
  contactNumber: text("contact_number"),
  email: text("email"),
  lifecycleState: text("lifecycle_state").notNull().default("EMPTY"),
  lifecycleUpdatedAt: text("lifecycle_updated_at").notNull().default(""),
  organizationId: text("organization_id").references(() => hospitalOrganizations.id, { onDelete: "restrict" }),
  synthetic: integer("synthetic", { mode: "boolean" }).notNull().default(false),
  ...timestamps,
}, (table) => [index("idx_cases_organization_updated").on(table.organizationId, table.updatedAt, table.id),index("idx_cases_organization_lifecycle").on(table.organizationId,table.lifecycleState,table.updatedAt)]);
export const patientExternalIdentifiers = sqliteTable("patient_external_identifiers", { id:text("id").primaryKey(),system:text("system").notNull(),value:text("value").notNull(),caseId:text("case_id").notNull().references(()=>cases.id,{onDelete:"cascade"}),organizationId:text("organization_id").references(()=>hospitalOrganizations.id,{onDelete:"restrict"}),createdAt:text("created_at").notNull() },(table)=>[uniqueIndex("idx_patient_external_identifier_org_system_value").on(table.organizationId,table.system,table.value),index("idx_patient_external_identifier_system_value_lookup").on(table.system,table.value)]);
export const patientSearchIndex = sqliteTable("patient_search_index", { caseId:text("case_id").primaryKey().references(()=>cases.id,{onDelete:"cascade"}),organizationId:text("organization_id").notNull().references(()=>hospitalOrganizations.id,{onDelete:"cascade"}),patientNameNormalized:text("patient_name_normalized").notNull(),caseCodeNormalized:text("case_code_normalized").notNull(),dobNormalized:text("dob_normalized").notNull(),contactNormalized:text("contact_normalized").notNull(),emailNormalized:text("email_normalized").notNull(),externalIdentifiersNormalized:text("external_identifiers_normalized").notNull(),searchText:text("search_text").notNull(),updatedAt:text("updated_at").notNull() },(table)=>[index("idx_patient_search_name").on(table.organizationId,table.patientNameNormalized),index("idx_patient_search_case_code").on(table.organizationId,table.caseCodeNormalized),index("idx_patient_search_contact").on(table.organizationId,table.contactNormalized),index("idx_patient_search_email").on(table.organizationId,table.emailNormalized)]);
export const bulkIngestions = sqliteTable("bulk_ingestions", { id:text("id").primaryKey(),organizationId:text("organization_id").references(()=>hospitalOrganizations.id,{onDelete:"restrict"}),status:text("status").notNull(),totalCount:integer("total_count").notNull(),uploadedCount:integer("uploaded_count").notNull().default(0),processedCount:integer("processed_count").notNull().default(0),reviewCount:integer("review_count").notNull().default(0),failedCount:integer("failed_count").notNull().default(0),createdAt:text("created_at").notNull(),updatedAt:text("updated_at").notNull() },(table)=>[index("idx_bulk_ingestions_organization").on(table.organizationId,table.updatedAt,table.id)]);

export const documents = sqliteTable("documents", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  name: text("name").notNull(),
  documentType: text("document_type").notNull(),
  mediaType: text("media_type").notNull(),
  pageCount: integer("page_count").notNull().default(1),
  objectKey: text("object_key"),
  uploadStatus: text("upload_status").notNull(),
  processingStatus: text("processing_status").notNull(),
  documentDate: text("document_date"),
  ...timestamps,
}, (table) => [index("idx_documents_case_id").on(table.caseId), index("idx_documents_case_status").on(table.caseId, table.processingStatus)]);
export const bulkIngestionItems = sqliteTable("bulk_ingestion_items", { id:text("id").primaryKey(),batchId:text("batch_id").notNull().references(()=>bulkIngestions.id,{onDelete:"cascade"}),ordinal:integer("ordinal").notNull(),filename:text("filename").notNull(),mediaType:text("media_type").notNull(),sizeBytes:integer("size_bytes").notNull(),patientIdentifierSystem:text("patient_identifier_system").notNull(),patientExternalId:text("patient_external_id").notNull(),patientLabel:text("patient_label").notNull(),dob:text("dob"),address:text("address"),contactNumber:text("contact_number"),email:text("email"),status:text("status").notNull(),objectKey:text("object_key"),caseId:text("case_id").references(()=>cases.id,{onDelete:"set null"}),documentId:text("document_id").references(()=>documents.id,{onDelete:"set null"}),error:text("error"),createdAt:text("created_at").notNull(),updatedAt:text("updated_at").notNull() },(table)=>[index("idx_bulk_ingestion_items_batch_status").on(table.batchId,table.status),index("idx_bulk_ingestion_items_patient").on(table.patientIdentifierSystem,table.patientExternalId)]);

export const documentPages = sqliteTable("document_pages", {
  id: text("id").primaryKey(),
  documentId: text("document_id").notNull().references(() => documents.id, { onDelete: "cascade" }),
  pageNumber: integer("page_number").notNull(),
  extractedText: text("extracted_text").notNull().default(""),
  confidence: real("confidence"),
  ...timestamps,
}, (table) => [index("idx_document_pages_document_id").on(table.documentId)]);
export const documentProcessingNotes = sqliteTable("document_processing_notes", { documentId:text("document_id").primaryKey().references(()=>documents.id,{onDelete:"cascade"}),note:text("note").notNull(),updatedAt:text("updated_at").notNull() });
export const documentExtractions = sqliteTable("document_extractions", {
  id: text("id").primaryKey(),
  documentId: text("document_id").notNull().references(() => documents.id, { onDelete: "cascade" }),
  method: text("method").notNull(),
  engine: text("engine").notNull(),
  model: text("model").notNull(),
  modelVersion: text("model_version").notNull(),
  status: text("status").notNull(),
  pageCount: integer("page_count").notNull(),
  confidence: real("confidence"),
  sourceSha256: text("source_sha256").notNull(),
  artifactKey: text("artifact_key").notNull(),
  classificationType: text("classification_type").notNull(),
  classificationConfidence: real("classification_confidence").notNull(),
  classificationReason: text("classification_reason").notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [index("idx_document_extractions_document_created").on(table.documentId, table.createdAt)]);
export const documentExtractionTextArtifacts = sqliteTable("document_extraction_text_artifacts", { extractionId:text("extraction_id").primaryKey().references(()=>documentExtractions.id,{onDelete:"cascade"}),artifactKey:text("artifact_key").notNull() });
export const documentMetadataCandidates = sqliteTable("document_metadata_candidates", { id:text("id").primaryKey(),documentId:text("document_id").notNull().references(()=>documents.id,{onDelete:"cascade"}),extractionId:text("extraction_id").notNull().references(()=>documentExtractions.id,{onDelete:"cascade"}),field:text("field").notNull(),value:text("value").notNull(),sourcePage:integer("source_page").notNull(),sourceText:text("source_text").notNull(),confidence:real("confidence").notNull(),status:text("status").notNull() },(table)=>[index("idx_document_metadata_candidates_document_field").on(table.documentId,table.field)]);

export const facts = sqliteTable("facts", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  documentId: text("document_id").notNull().references(() => documents.id, { onDelete: "cascade" }),
  concept: text("concept").notNull(),
  originalConcept: text("original_concept").notNull(),
  numericValue: real("numeric_value"),
  textValue: text("text_value"),
  unit: text("unit"),
  observedDate: text("observed_date"),
  datePrecision: text("date_precision").notNull(),
  sourcePage: integer("source_page").notNull(),
  sourceText: text("source_text").notNull(),
  extractionConfidence: real("extraction_confidence"),
  ...timestamps,
}, (table) => [index("idx_facts_case_concept_date").on(table.caseId, table.concept, table.observedDate), index("idx_facts_document_id").on(table.documentId)]);
export const factTemporal = sqliteTable("fact_temporal", { factId:text("fact_id").primaryKey().references(()=>facts.id,{onDelete:"cascade"}),eventDate:text("event_date"),dateType:text("date_type"),precision:text("precision"),status:text("status").notNull(),sourcePage:integer("source_page"),sourceText:text("source_text"),confidence:text("confidence") },(table)=>[index("idx_fact_temporal_date_type").on(table.eventDate,table.dateType)]);
export const factObservationDetails = sqliteTable("fact_observation_details", { factId:text("fact_id").primaryKey().references(()=>facts.id,{onDelete:"cascade"}),referenceLow:real("reference_low"),referenceHigh:real("reference_high"),referenceText:text("reference_text"),specimen:text("specimen"),unitStatus:text("unit_status").notNull(),extractionMethod:text("extraction_method").notNull() });
export const factExtractionDetails = sqliteTable("fact_extraction_details", { factId:text("fact_id").primaryKey().references(()=>facts.id,{onDelete:"cascade"}),rawValue:text("raw_value").notNull(),rawUnit:text("raw_unit"),conversionFactor:real("conversion_factor") });
export const factSourceSpans = sqliteTable("fact_source_spans", { factId:text("fact_id").primaryKey().references(()=>facts.id,{onDelete:"cascade"}),extractionId:text("extraction_id").notNull().references(()=>documentExtractions.id,{onDelete:"cascade"}),blockIds:text("block_ids",{mode:"json"}).notNull(),bbox:text("bbox",{mode:"json"}),confidence:real("confidence").notNull() },(table)=>[index("idx_fact_source_spans_extraction").on(table.extractionId)]);
export const documentClinicalDates = sqliteTable("document_clinical_dates", { id:text("id").primaryKey(),documentId:text("document_id").notNull().references(()=>documents.id,{onDelete:"cascade"}),value:text("value").notNull(),type:text("type").notNull(),precision:text("precision").notNull(),sourcePage:integer("source_page").notNull(),sourceText:text("source_text").notNull(),confidence:text("confidence").notNull() },(table)=>[index("idx_document_clinical_dates_document").on(table.documentId),index("idx_document_clinical_dates_value_type").on(table.value,table.type)]);
export const evidenceTerminologyCandidates = sqliteTable("evidence_terminology_candidates", { id:text("id").primaryKey(),caseId:text("case_id").notNull().references(()=>cases.id,{onDelete:"cascade"}),subjectType:text("subject_type").notNull(),subjectId:text("subject_id").notNull(),sourceSystem:text("source_system").notNull(),sourceCode:text("source_code").notNull(),sourceVersion:text("source_version").notNull(),sourceUri:text("source_uri").notNull(),label:text("label").notNull(),semanticType:text("semantic_type"),units:text("units",{mode:"json"}).notNull(),status:text("status").notNull(),reason:text("reason").notNull(),resolvedAt:text("resolved_at").notNull() },(table)=>[uniqueIndex("idx_evidence_terminology_candidate_unique").on(table.subjectType,table.subjectId,table.sourceSystem,table.sourceCode,table.sourceVersion),index("idx_evidence_terminology_candidates_case_subject").on(table.caseId,table.subjectType,table.subjectId)]);

export const claims = sqliteTable("claims", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  documentId: text("document_id").notNull().references(() => documents.id, { onDelete: "cascade" }),
  claimText: text("claim_text").notNull(),
  claimDate: text("claim_date"),
  sourcePage: integer("source_page").notNull(),
  sourceText: text("source_text").notNull(),
  extractionConfidence: real("extraction_confidence"),
  ...timestamps,
}, (table) => [index("idx_claims_case_id").on(table.caseId)]);
export const claimSourceSpans = sqliteTable("claim_source_spans", { claimId:text("claim_id").primaryKey().references(()=>claims.id,{onDelete:"cascade"}),extractionId:text("extraction_id").notNull().references(()=>documentExtractions.id,{onDelete:"cascade"}),blockIds:text("block_ids",{mode:"json"}).notNull(),bbox:text("bbox",{mode:"json"}),confidence:real("confidence").notNull(),category:text("category").notNull(),reviewStatus:text("review_status").notNull() },(table)=>[index("idx_claim_source_spans_extraction").on(table.extractionId)]);
export const claimRuleBindings = sqliteTable("claim_rule_bindings", {
  claimId: text("claim_id").primaryKey().references(() => claims.id, { onDelete: "cascade" }),
  claimType: text("claim_type"),
  supportConcepts: text("support_concepts", { mode: "json" }),
  gapRule: text("gap_rule"),
  referencedDocument: text("referenced_document"),
  expectedConcept: text("expected_concept"),
  lookbackDays: integer("lookback_days"),
  evidenceLabels: text("evidence_labels", { mode: "json" }),
});

export const evidenceSourceSpans = sqliteTable("evidence_source_spans", {
  id: text("id").primaryKey(),
  extractionId: text("extraction_id").notNull().references(() => documentExtractions.id, { onDelete: "cascade" }),
  documentId: text("document_id").notNull().references(() => documents.id, { onDelete: "cascade" }),
  pageNumber: integer("page_number").notNull(),
  sourceText: text("source_text").notNull(),
  charStart: integer("char_start"),
  charEnd: integer("char_end"),
  blockIds: text("block_ids", { mode: "json" }).notNull(),
  bbox: text("bbox", { mode: "json" }),
  confidence: real("confidence").notNull(),
  method: text("method").notNull(),
  engine: text("engine").notNull(),
  model: text("model").notNull(),
  modelVersion: text("model_version").notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [index("idx_evidence_source_spans_document_page").on(table.documentId, table.pageNumber), index("idx_evidence_source_spans_extraction").on(table.extractionId)]);
export const evidenceSourceLinks = sqliteTable("evidence_source_links", {
  id: text("id").primaryKey(),
  sourceSpanId: text("source_span_id").notNull().references(() => evidenceSourceSpans.id, { onDelete: "cascade" }),
  subjectType: text("subject_type").notNull(),
  subjectId: text("subject_id").notNull(),
  role: text("role").notNull(),
  ordinal: integer("ordinal").notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [uniqueIndex("idx_evidence_source_links_subject_span").on(table.subjectType, table.subjectId, table.sourceSpanId), index("idx_evidence_source_links_subject").on(table.subjectType, table.subjectId)]);

export const medications = sqliteTable("medications", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  documentId: text("document_id").notNull().references(() => documents.id, { onDelete: "cascade" }),
  drugName: text("drug_name").notNull(),
  normalizedDrug: text("normalized_drug").notNull(),
  ingredient: text("ingredient"),
  brand: text("brand"),
  strength: text("strength"),
  strengthUnit: text("strength_unit"),
  dose: text("dose"),
  doseAmount: text("dose_amount"),
  doseUnit: text("dose_unit"),
  doseForm: text("dose_form"),
  frequency: text("frequency"),
  route: text("route"),
  duration: text("duration"),
  status: text("status").notNull(),
  startDate: text("start_date"),
  stopDate: text("stop_date"),
  prescriber: text("prescriber"),
  sourcePage: integer("source_page").notNull(),
  sourceText: text("source_text").notNull(),
  extractionConfidence: real("extraction_confidence"),
  reviewStatus: text("review_status").notNull().default("REVIEW_REQUIRED"),
  ...timestamps,
}, (table) => [index("idx_medications_case_drug").on(table.caseId, table.normalizedDrug)]);

export const documentReferences = sqliteTable("document_references", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  documentId: text("document_id").notNull().references(() => documents.id, { onDelete: "cascade" }),
  label: text("label").notNull(),
  targetDocumentType: text("target_document_type"),
  referencedDate: text("referenced_date"),
  resolvedDocumentId: text("resolved_document_id").references(() => documents.id, { onDelete: "set null" }),
  status: text("status").notNull(),
  sourcePage: integer("source_page").notNull(),
  sourceText: text("source_text").notNull(),
  extractionConfidence: real("extraction_confidence").notNull(),
  reviewStatus: text("review_status").notNull(),
  ...timestamps,
}, (table) => [index("idx_document_references_case_status").on(table.caseId, table.status), index("idx_document_references_document").on(table.documentId)]);

export const events = sqliteTable("events", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  documentId: text("document_id").references(() => documents.id, { onDelete: "set null" }),
  eventType: text("event_type").notNull(),
  eventDate: text("event_date"),
  datePrecision: text("date_precision"),
  sourcePage: integer("source_page"),
  sourceText: text("source_text"),
  extractionConfidence: real("extraction_confidence"),
  reviewStatus: text("review_status"),
  payload: text("payload", { mode: "json" }),
  ...timestamps,
}, (table) => [index("idx_events_case_date").on(table.caseId, table.eventDate)]);

export const relationships = sqliteTable("relationships", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  fromId: text("from_id").notNull(),
  toId: text("to_id").notNull(),
  relationshipType: text("relationship_type").notNull(),
  rationale: text("rationale").notNull(),
  ...timestamps,
}, (table) => [index("idx_relationships_case_type").on(table.caseId, table.relationshipType), index("idx_relationships_from_id").on(table.fromId), index("idx_relationships_to_id").on(table.toId)]);

export const conflicts = sqliteTable("conflicts", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  concept: text("concept").notNull(),
  evidenceAId: text("evidence_a_id").notNull(),
  evidenceBId: text("evidence_b_id").notNull(),
  status: text("status").notNull(),
  explanation: text("explanation").notNull(),
  ...timestamps,
}, (table) => [index("idx_conflicts_case_status").on(table.caseId, table.status)]);

export const evidenceGaps = sqliteTable("evidence_gaps", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  claimId: text("claim_id").references(() => claims.id, { onDelete: "set null" }),
  gapType: text("gap_type").notNull(),
  status: text("status").notNull(),
  missingItems: text("missing_items", { mode: "json" }).notNull(),
  ...timestamps,
}, (table) => [index("idx_evidence_gaps_case_status").on(table.caseId, table.status)]);

export const processingRuns = sqliteTable("processing_runs", {
  id: text("id").primaryKey(),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "cascade" }),
  status: text("status").notNull(),
  currentStage: text("current_stage").notNull(),
  startedAt: text("started_at").notNull(),
  completedAt: text("completed_at"),
  summary: text("summary", { mode: "json" }),
  runSequence: integer("run_sequence"),
  rulesetVersion: text("ruleset_version"),
  sourceSnapshotSha256: text("source_snapshot_sha256"),
  isCurrent: integer("is_current", { mode: "boolean" }).notNull().default(false),
  initiatedBy: text("initiated_by"),
  error: text("error"),
}, (table) => [index("idx_processing_runs_case_id").on(table.caseId),uniqueIndex("idx_processing_runs_case_sequence").on(table.caseId,table.runSequence)]);

export const processingRunDocuments = sqliteTable("processing_run_documents", { id:text("id").primaryKey(),runId:text("run_id").notNull().references(()=>processingRuns.id,{onDelete:"cascade"}),documentId:text("document_id").notNull().references(()=>documents.id,{onDelete:"cascade"}),extractionId:text("extraction_id").references(()=>documentExtractions.id,{onDelete:"set null"}),sourceSha256:text("source_sha256"),processingStatus:text("processing_status").notNull(),createdAt:text("created_at").notNull() },(table)=>[uniqueIndex("idx_processing_run_documents_run_document").on(table.runId,table.documentId),index("idx_processing_run_documents_document").on(table.documentId)]);
export const processingRunArtifacts = sqliteTable("processing_run_artifacts", { runId:text("run_id").primaryKey().references(()=>processingRuns.id,{onDelete:"cascade"}),artifactKey:text("artifact_key").notNull(),sha256:text("sha256").notNull(),schemaVersion:text("schema_version").notNull(),createdAt:text("created_at").notNull() });
export const auditChanges = sqliteTable("audit_changes", { id:text("id").primaryKey(),runId:text("run_id").notNull().references(()=>processingRuns.id,{onDelete:"cascade"}),caseId:text("case_id").notNull().references(()=>cases.id,{onDelete:"cascade"}),findingId:text("finding_id").notNull(),concept:text("concept").notNull(),fromFactId:text("from_fact_id").notNull(),toFactId:text("to_fact_id").notNull(),fromValue:text("from_value",{mode:"json"}).notNull(),toValue:text("to_value",{mode:"json"}).notNull(),basis:text("basis").notNull(),createdAt:text("created_at").notNull() },(table)=>[index("idx_audit_changes_run").on(table.runId),index("idx_audit_changes_case_concept").on(table.caseId,table.concept)]);
export const auditConflicts = sqliteTable("audit_conflicts", { id:text("id").primaryKey(),runId:text("run_id").notNull().references(()=>processingRuns.id,{onDelete:"cascade"}),caseId:text("case_id").notNull().references(()=>cases.id,{onDelete:"cascade"}),findingId:text("finding_id").notNull(),kind:text("kind").notNull(),concept:text("concept").notNull(),evidenceAId:text("evidence_a_id").notNull(),evidenceBId:text("evidence_b_id").notNull(),status:text("status").notNull(),explanation:text("explanation").notNull(),payload:text("payload",{mode:"json"}).notNull(),createdAt:text("created_at").notNull() },(table)=>[index("idx_audit_conflicts_run").on(table.runId),index("idx_audit_conflicts_case_status").on(table.caseId,table.status)]);
export const auditEvidenceGaps = sqliteTable("audit_evidence_gaps", { id:text("id").primaryKey(),runId:text("run_id").notNull().references(()=>processingRuns.id,{onDelete:"cascade"}),caseId:text("case_id").notNull().references(()=>cases.id,{onDelete:"cascade"}),findingId:text("finding_id").notNull(),kind:text("kind").notNull(),subjectType:text("subject_type").notNull(),subjectId:text("subject_id").notNull(),status:text("status").notNull(),evidenceLocated:text("evidence_located",{mode:"json"}).notNull(),evidenceNotLocated:text("evidence_not_located",{mode:"json"}).notNull(),basis:text("basis").notNull(),createdAt:text("created_at").notNull() },(table)=>[index("idx_audit_gaps_run").on(table.runId),index("idx_audit_gaps_case_status").on(table.caseId,table.status)]);
export const auditRelationships = sqliteTable("audit_relationships", { id:text("id").primaryKey(),runId:text("run_id").notNull().references(()=>processingRuns.id,{onDelete:"cascade"}),caseId:text("case_id").notNull().references(()=>cases.id,{onDelete:"cascade"}),findingId:text("finding_id").notNull(),fromType:text("from_type").notNull(),fromId:text("from_id").notNull(),toType:text("to_type").notNull(),toId:text("to_id").notNull(),relationshipType:text("relationship_type").notNull(),rationale:text("rationale").notNull(),createdAt:text("created_at").notNull() },(table)=>[index("idx_audit_relationships_run").on(table.runId),index("idx_audit_relationships_case_type").on(table.caseId,table.relationshipType)]);

export const actorAuditEvents = sqliteTable("actor_audit_events", {
  id: text("id").primaryKey(),
  organizationId: text("organization_id").notNull().references(() => hospitalOrganizations.id, { onDelete: "restrict" }),
  actorUserId: text("actor_user_id").notNull(),
  actorEmail: text("actor_email").notNull(),
  actorDisplayName: text("actor_display_name"),
  actorRole: text("actor_role").notNull(),
  requestId: text("request_id").notNull(),
  action: text("action").notNull(),
  targetType: text("target_type").notNull(),
  targetId: text("target_id").notNull(),
  caseId: text("case_id").references(() => cases.id, { onDelete: "restrict" }),
  metadata: text("metadata_json", { mode: "json" }).notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [
  index("idx_actor_audit_org_time").on(table.organizationId, table.createdAt, table.id),
  index("idx_actor_audit_case_time").on(table.organizationId, table.caseId, table.createdAt, table.id),
]);
export const interoperabilityTransformations = sqliteTable("interoperability_transformations", {
  id: text("id").primaryKey(),
  organizationId: text("organization_id").notNull().references(() => hospitalOrganizations.id, { onDelete: "restrict" }),
  caseId: text("case_id").notNull().references(() => cases.id, { onDelete: "restrict" }),
  sourceRunId: text("source_run_id").references(() => processingRuns.id, { onDelete: "set null" }),
  target: text("target").notNull(),
  profile: text("profile").notNull(),
  mediaType: text("media_type").notNull(),
  artifactObjectKey: text("artifact_object_key").notNull(),
  artifactSha256: text("artifact_sha256").notNull(),
  validation: text("validation_json", { mode: "json" }).notNull(),
  semanticSummary: text("semantic_summary_json", { mode: "json" }).notNull(),
  actorUserId: text("actor_user_id").notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [index("idx_transformations_case_time").on(table.organizationId, table.caseId, table.createdAt)]);
export const semanticIntegrityFindings = sqliteTable("semantic_integrity_findings", {
  id: text("id").primaryKey(),
  transformationId: text("transformation_id").notNull().references(() => interoperabilityTransformations.id, { onDelete: "cascade" }),
  sourcePath: text("source_path").notNull(),
  targetPath: text("target_path"),
  status: text("status").notNull(),
  severity: text("severity").notNull(),
  reason: text("reason"),
  createdAt: text("created_at").notNull(),
}, (table) => [index("idx_semantic_findings_status").on(table.transformationId, table.status, table.severity)]);
export const interoperabilityImportAnalyses = sqliteTable("interoperability_import_analyses", {
  id: text("id").primaryKey(),
  organizationId: text("organization_id").notNull().references(() => hospitalOrganizations.id, { onDelete: "restrict" }),
  sourceFormat: text("source_format").notNull(),
  sourceSha256: text("source_sha256").notNull(),
  sourceObjectKey: text("source_object_key").notNull(),
  canonicalObjectKey: text("canonical_object_key").notNull(),
  semanticSummary: text("semantic_summary_json", { mode: "json" }).notNull(),
  actorUserId: text("actor_user_id").notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [index("idx_import_analyses_org_time").on(table.organizationId, table.createdAt, table.id)]);

export const terminologySources = sqliteTable("terminology_sources", { key: text("key").primaryKey(), name: text("name").notNull(), sourceUri: text("source_uri").notNull(), licenseStatus: text("license_status").notNull(), apiConfigured: integer("api_configured", { mode: "boolean" }).notNull().default(false), ...timestamps });
export const terminologyReleases = sqliteTable("terminology_releases", { id: text("id").primaryKey(), sourceKey: text("source_key").notNull().references(() => terminologySources.key), version: text("version").notNull(), releaseDate: text("release_date").notNull(), importDate: text("import_date").notNull(), status: text("status").notNull(), format: text("format").notNull(), checksumAlgorithm: text("checksum_algorithm").notNull(), checksumExpected: text("checksum_expected"), checksumActual: text("checksum_actual"), checksumVerified: integer("checksum_verified", { mode: "boolean" }), recordCount: integer("record_count").notNull(), artifactKey: text("artifact_key"), previousReleaseId: text("previous_release_id") }, (table) => [index("idx_term_release_source_status").on(table.sourceKey, table.status), index("idx_term_release_source_version").on(table.sourceKey, table.version)]);
export const terminologyReleaseGovernance = sqliteTable("terminology_release_governance", { releaseId: text("release_id").primaryKey().references(() => terminologyReleases.id, { onDelete: "cascade" }), licenseName: text("license_name").notNull(), licenseStatus: text("license_status").notNull(), acceptedAt: text("accepted_at").notNull() });
export const terminologyImports = sqliteTable("terminology_imports", { id: text("id").primaryKey(), releaseId: text("release_id"), sourceKey: text("source_key").notNull(), filename: text("filename").notNull(), status: text("status").notNull(), report: text("report", { mode: "json" }).notNull(), startedAt: text("started_at").notNull(), completedAt: text("completed_at").notNull() }, (table) => [index("idx_term_import_source_status").on(table.sourceKey, table.status)]);
export const terminologyConcepts = sqliteTable("terminology_concepts", { id: text("id").primaryKey(), releaseId: text("release_id").notNull().references(() => terminologyReleases.id, { onDelete: "cascade" }), caretraceId: text("caretrace_id").notNull(), sourceSystem: text("source_system").notNull(), sourceCode: text("source_code").notNull(), sourceVersion: text("source_version").notNull(), sourceUri: text("source_uri").notNull(), sourceLabel: text("source_label").notNull(), label: text("label").notNull(), normalizedLabel: text("normalized_label").notNull(), domain: text("domain").notNull(), category: text("category").notNull(), semanticType: text("semantic_type").notNull(), status: text("status").notNull(), importedAt: text("imported_at").notNull() }, (table) => [index("idx_term_concept_release_code").on(table.releaseId, table.sourceCode), index("idx_term_concept_caretrace").on(table.caretraceId), index("idx_term_concept_label").on(table.normalizedLabel)]);
export const terminologyAliases = sqliteTable("terminology_aliases", { id: text("id").primaryKey(), conceptId: text("concept_id").notNull().references(() => terminologyConcepts.id, { onDelete: "cascade" }), alias: text("alias").notNull(), normalizedAlias: text("normalized_alias").notNull() }, (table) => [index("idx_term_alias_normalized").on(table.normalizedAlias), index("idx_term_alias_concept").on(table.conceptId)]);
export const terminologyUnits = sqliteTable("terminology_units", { id: text("id").primaryKey(), conceptId: text("concept_id").notNull().references(() => terminologyConcepts.id, { onDelete: "cascade" }), unit: text("unit").notNull() }, (table) => [index("idx_term_unit_concept").on(table.conceptId)]);
export const terminologyRelationships = sqliteTable("terminology_relationships", { id: text("id").primaryKey(), conceptId: text("concept_id").notNull().references(() => terminologyConcepts.id, { onDelete: "cascade" }), type: text("type").notNull(), targetSourceCode: text("target_source_code").notNull(), group: text("relationship_group"), active: integer("active", { mode: "boolean" }).notNull() }, (table) => [index("idx_term_relationship_concept").on(table.conceptId), index("idx_term_relationship_target").on(table.targetSourceCode)]);
export const terminologyMappings = sqliteTable("terminology_mappings", { id: text("id").primaryKey(), conceptId: text("concept_id").notNull().references(() => terminologyConcepts.id, { onDelete: "cascade" }), system: text("system").notNull(), code: text("code"), sourceVersion: text("source_version").notNull(), sourceUri: text("source_uri").notNull(), relationship: text("relationship").notNull(), status: text("status").notNull() }, (table) => [index("idx_term_mapping_concept").on(table.conceptId), index("idx_term_mapping_system_code").on(table.system, table.code)]);
export const terminologyApiCache = sqliteTable("terminology_api_cache", { id: text("id").primaryKey(), sourceKey: text("source_key").notNull(), cacheKey: text("cache_key").notNull(), response: text("response", { mode: "json" }).notNull(), expiresAt: text("expires_at").notNull(), createdAt: text("created_at").notNull() }, (table) => [index("idx_term_cache_source_key").on(table.sourceKey, table.cacheKey), index("idx_term_cache_expiry").on(table.expiresAt)]);
