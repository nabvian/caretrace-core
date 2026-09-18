CREATE TABLE `bulk_ingestion_items` (
	`id` text PRIMARY KEY NOT NULL,
	`batch_id` text NOT NULL,
	`ordinal` integer NOT NULL,
	`filename` text NOT NULL,
	`media_type` text NOT NULL,
	`size_bytes` integer NOT NULL,
	`patient_identifier_system` text NOT NULL,
	`patient_external_id` text NOT NULL,
	`patient_label` text NOT NULL,
	`dob` text,
	`status` text NOT NULL,
	`object_key` text,
	`case_id` text,
	`document_id` text,
	`error` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`batch_id`) REFERENCES `bulk_ingestions`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE INDEX `idx_bulk_ingestion_items_batch_status` ON `bulk_ingestion_items` (`batch_id`,`status`);--> statement-breakpoint
CREATE INDEX `idx_bulk_ingestion_items_patient` ON `bulk_ingestion_items` (`patient_identifier_system`,`patient_external_id`);--> statement-breakpoint
CREATE TABLE `bulk_ingestions` (
	`id` text PRIMARY KEY NOT NULL,
	`status` text NOT NULL,
	`total_count` integer NOT NULL,
	`uploaded_count` integer DEFAULT 0 NOT NULL,
	`processed_count` integer DEFAULT 0 NOT NULL,
	`review_count` integer DEFAULT 0 NOT NULL,
	`failed_count` integer DEFAULT 0 NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `claim_source_spans` (
	`claim_id` text PRIMARY KEY NOT NULL,
	`extraction_id` text NOT NULL,
	`block_ids` text NOT NULL,
	`bbox` text,
	`confidence` real NOT NULL,
	`category` text NOT NULL,
	`review_status` text NOT NULL,
	FOREIGN KEY (`claim_id`) REFERENCES `claims`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`extraction_id`) REFERENCES `document_extractions`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_claim_source_spans_extraction` ON `claim_source_spans` (`extraction_id`);--> statement-breakpoint
CREATE TABLE `document_extraction_text_artifacts` (
	`extraction_id` text PRIMARY KEY NOT NULL,
	`artifact_key` text NOT NULL,
	FOREIGN KEY (`extraction_id`) REFERENCES `document_extractions`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `document_metadata_candidates` (
	`id` text PRIMARY KEY NOT NULL,
	`document_id` text NOT NULL,
	`extraction_id` text NOT NULL,
	`field` text NOT NULL,
	`value` text NOT NULL,
	`source_page` integer NOT NULL,
	`source_text` text NOT NULL,
	`confidence` real NOT NULL,
	`status` text NOT NULL,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`extraction_id`) REFERENCES `document_extractions`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_document_metadata_candidates_document_field` ON `document_metadata_candidates` (`document_id`,`field`);--> statement-breakpoint
CREATE TABLE `patient_external_identifiers` (
	`id` text PRIMARY KEY NOT NULL,
	`system` text NOT NULL,
	`value` text NOT NULL,
	`case_id` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_patient_external_identifier_system_value` ON `patient_external_identifiers` (`system`,`value`);