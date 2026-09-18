CREATE TABLE `cases` (
	`id` text PRIMARY KEY NOT NULL,
	`case_code` text NOT NULL,
	`patient_label` text NOT NULL,
	`dob` text,
	`synthetic` integer DEFAULT false NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `cases_case_code_unique` ON `cases` (`case_code`);--> statement-breakpoint
CREATE TABLE `claims` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`document_id` text NOT NULL,
	`claim_text` text NOT NULL,
	`claim_date` text,
	`source_page` integer NOT NULL,
	`source_text` text NOT NULL,
	`extraction_confidence` real,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_claims_case_id` ON `claims` (`case_id`);--> statement-breakpoint
CREATE TABLE `conflicts` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`concept` text NOT NULL,
	`evidence_a_id` text NOT NULL,
	`evidence_b_id` text NOT NULL,
	`status` text NOT NULL,
	`explanation` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_conflicts_case_status` ON `conflicts` (`case_id`,`status`);--> statement-breakpoint
CREATE TABLE `document_pages` (
	`id` text PRIMARY KEY NOT NULL,
	`document_id` text NOT NULL,
	`page_number` integer NOT NULL,
	`extracted_text` text DEFAULT '' NOT NULL,
	`confidence` real,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_document_pages_document_id` ON `document_pages` (`document_id`);--> statement-breakpoint
CREATE TABLE `documents` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`name` text NOT NULL,
	`document_type` text NOT NULL,
	`media_type` text NOT NULL,
	`page_count` integer DEFAULT 1 NOT NULL,
	`object_key` text,
	`upload_status` text NOT NULL,
	`processing_status` text NOT NULL,
	`document_date` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_documents_case_id` ON `documents` (`case_id`);--> statement-breakpoint
CREATE INDEX `idx_documents_case_status` ON `documents` (`case_id`,`processing_status`);--> statement-breakpoint
CREATE TABLE `events` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`document_id` text,
	`event_type` text NOT NULL,
	`event_date` text,
	`payload` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE INDEX `idx_events_case_date` ON `events` (`case_id`,`event_date`);--> statement-breakpoint
CREATE TABLE `evidence_gaps` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`claim_id` text,
	`gap_type` text NOT NULL,
	`status` text NOT NULL,
	`missing_items` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`claim_id`) REFERENCES `claims`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE INDEX `idx_evidence_gaps_case_status` ON `evidence_gaps` (`case_id`,`status`);--> statement-breakpoint
CREATE TABLE `facts` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`document_id` text NOT NULL,
	`concept` text NOT NULL,
	`original_concept` text NOT NULL,
	`numeric_value` real,
	`text_value` text,
	`unit` text,
	`observed_date` text,
	`date_precision` text NOT NULL,
	`source_page` integer NOT NULL,
	`source_text` text NOT NULL,
	`extraction_confidence` real,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_facts_case_concept_date` ON `facts` (`case_id`,`concept`,`observed_date`);--> statement-breakpoint
CREATE INDEX `idx_facts_document_id` ON `facts` (`document_id`);--> statement-breakpoint
CREATE TABLE `medications` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`document_id` text NOT NULL,
	`drug_name` text NOT NULL,
	`normalized_drug` text NOT NULL,
	`dose` text,
	`frequency` text,
	`route` text,
	`status` text NOT NULL,
	`start_date` text,
	`stop_date` text,
	`source_page` integer NOT NULL,
	`source_text` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_medications_case_drug` ON `medications` (`case_id`,`normalized_drug`);--> statement-breakpoint
CREATE TABLE `processing_runs` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`status` text NOT NULL,
	`current_stage` text NOT NULL,
	`started_at` text NOT NULL,
	`completed_at` text,
	`summary` text,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_processing_runs_case_id` ON `processing_runs` (`case_id`);--> statement-breakpoint
CREATE TABLE `relationships` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`from_id` text NOT NULL,
	`to_id` text NOT NULL,
	`relationship_type` text NOT NULL,
	`rationale` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_relationships_case_type` ON `relationships` (`case_id`,`relationship_type`);--> statement-breakpoint
CREATE INDEX `idx_relationships_from_id` ON `relationships` (`from_id`);--> statement-breakpoint
CREATE INDEX `idx_relationships_to_id` ON `relationships` (`to_id`);--> statement-breakpoint
PRAGMA optimize;
