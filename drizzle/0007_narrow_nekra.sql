CREATE TABLE `audit_changes` (
	`id` text PRIMARY KEY NOT NULL,
	`run_id` text NOT NULL,
	`case_id` text NOT NULL,
	`finding_id` text NOT NULL,
	`concept` text NOT NULL,
	`from_fact_id` text NOT NULL,
	`to_fact_id` text NOT NULL,
	`from_value` text NOT NULL,
	`to_value` text NOT NULL,
	`basis` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`run_id`) REFERENCES `processing_runs`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_audit_changes_run` ON `audit_changes` (`run_id`);--> statement-breakpoint
CREATE INDEX `idx_audit_changes_case_concept` ON `audit_changes` (`case_id`,`concept`);--> statement-breakpoint
CREATE TABLE `audit_conflicts` (
	`id` text PRIMARY KEY NOT NULL,
	`run_id` text NOT NULL,
	`case_id` text NOT NULL,
	`finding_id` text NOT NULL,
	`kind` text NOT NULL,
	`concept` text NOT NULL,
	`evidence_a_id` text NOT NULL,
	`evidence_b_id` text NOT NULL,
	`status` text NOT NULL,
	`explanation` text NOT NULL,
	`payload` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`run_id`) REFERENCES `processing_runs`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_audit_conflicts_run` ON `audit_conflicts` (`run_id`);--> statement-breakpoint
CREATE INDEX `idx_audit_conflicts_case_status` ON `audit_conflicts` (`case_id`,`status`);--> statement-breakpoint
CREATE TABLE `audit_evidence_gaps` (
	`id` text PRIMARY KEY NOT NULL,
	`run_id` text NOT NULL,
	`case_id` text NOT NULL,
	`finding_id` text NOT NULL,
	`kind` text NOT NULL,
	`subject_type` text NOT NULL,
	`subject_id` text NOT NULL,
	`status` text NOT NULL,
	`evidence_located` text NOT NULL,
	`evidence_not_located` text NOT NULL,
	`basis` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`run_id`) REFERENCES `processing_runs`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_audit_gaps_run` ON `audit_evidence_gaps` (`run_id`);--> statement-breakpoint
CREATE INDEX `idx_audit_gaps_case_status` ON `audit_evidence_gaps` (`case_id`,`status`);--> statement-breakpoint
CREATE TABLE `audit_relationships` (
	`id` text PRIMARY KEY NOT NULL,
	`run_id` text NOT NULL,
	`case_id` text NOT NULL,
	`finding_id` text NOT NULL,
	`from_type` text NOT NULL,
	`from_id` text NOT NULL,
	`to_type` text NOT NULL,
	`to_id` text NOT NULL,
	`relationship_type` text NOT NULL,
	`rationale` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`run_id`) REFERENCES `processing_runs`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_audit_relationships_run` ON `audit_relationships` (`run_id`);--> statement-breakpoint
CREATE INDEX `idx_audit_relationships_case_type` ON `audit_relationships` (`case_id`,`relationship_type`);--> statement-breakpoint
CREATE TABLE `document_references` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`document_id` text NOT NULL,
	`label` text NOT NULL,
	`target_document_type` text,
	`referenced_date` text,
	`resolved_document_id` text,
	`status` text NOT NULL,
	`source_page` integer NOT NULL,
	`source_text` text NOT NULL,
	`extraction_confidence` real NOT NULL,
	`review_status` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`resolved_document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE INDEX `idx_document_references_case_status` ON `document_references` (`case_id`,`status`);--> statement-breakpoint
CREATE INDEX `idx_document_references_document` ON `document_references` (`document_id`);--> statement-breakpoint
CREATE TABLE `evidence_source_links` (
	`id` text PRIMARY KEY NOT NULL,
	`source_span_id` text NOT NULL,
	`subject_type` text NOT NULL,
	`subject_id` text NOT NULL,
	`role` text NOT NULL,
	`ordinal` integer NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`source_span_id`) REFERENCES `evidence_source_spans`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_evidence_source_links_subject_span` ON `evidence_source_links` (`subject_type`,`subject_id`,`source_span_id`);--> statement-breakpoint
CREATE INDEX `idx_evidence_source_links_subject` ON `evidence_source_links` (`subject_type`,`subject_id`);--> statement-breakpoint
CREATE TABLE `evidence_source_spans` (
	`id` text PRIMARY KEY NOT NULL,
	`extraction_id` text NOT NULL,
	`document_id` text NOT NULL,
	`page_number` integer NOT NULL,
	`source_text` text NOT NULL,
	`char_start` integer,
	`char_end` integer,
	`block_ids` text NOT NULL,
	`bbox` text,
	`confidence` real NOT NULL,
	`method` text NOT NULL,
	`engine` text NOT NULL,
	`model` text NOT NULL,
	`model_version` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`extraction_id`) REFERENCES `document_extractions`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_evidence_source_spans_document_page` ON `evidence_source_spans` (`document_id`,`page_number`);--> statement-breakpoint
CREATE INDEX `idx_evidence_source_spans_extraction` ON `evidence_source_spans` (`extraction_id`);--> statement-breakpoint
CREATE TABLE `processing_run_artifacts` (
	`run_id` text PRIMARY KEY NOT NULL,
	`artifact_key` text NOT NULL,
	`sha256` text NOT NULL,
	`schema_version` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`run_id`) REFERENCES `processing_runs`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `processing_run_documents` (
	`id` text PRIMARY KEY NOT NULL,
	`run_id` text NOT NULL,
	`document_id` text NOT NULL,
	`extraction_id` text,
	`source_sha256` text,
	`processing_status` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`run_id`) REFERENCES `processing_runs`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`extraction_id`) REFERENCES `document_extractions`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_processing_run_documents_run_document` ON `processing_run_documents` (`run_id`,`document_id`);--> statement-breakpoint
CREATE INDEX `idx_processing_run_documents_document` ON `processing_run_documents` (`document_id`);--> statement-breakpoint
ALTER TABLE `events` ADD `date_precision` text;--> statement-breakpoint
ALTER TABLE `events` ADD `source_page` integer;--> statement-breakpoint
ALTER TABLE `events` ADD `source_text` text;--> statement-breakpoint
ALTER TABLE `events` ADD `extraction_confidence` real;--> statement-breakpoint
ALTER TABLE `events` ADD `review_status` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `ingredient` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `brand` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `strength` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `strength_unit` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `dose_amount` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `dose_unit` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `dose_form` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `duration` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `prescriber` text;--> statement-breakpoint
ALTER TABLE `medications` ADD `extraction_confidence` real;--> statement-breakpoint
ALTER TABLE `medications` ADD `review_status` text DEFAULT 'REVIEW_REQUIRED' NOT NULL;--> statement-breakpoint
ALTER TABLE `processing_runs` ADD `run_sequence` integer;--> statement-breakpoint
ALTER TABLE `processing_runs` ADD `ruleset_version` text;--> statement-breakpoint
ALTER TABLE `processing_runs` ADD `source_snapshot_sha256` text;--> statement-breakpoint
ALTER TABLE `processing_runs` ADD `is_current` integer DEFAULT false NOT NULL;--> statement-breakpoint
ALTER TABLE `processing_runs` ADD `initiated_by` text;--> statement-breakpoint
ALTER TABLE `processing_runs` ADD `error` text;