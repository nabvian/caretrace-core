CREATE TABLE `document_extractions` (
	`id` text PRIMARY KEY NOT NULL,
	`document_id` text NOT NULL,
	`method` text NOT NULL,
	`engine` text NOT NULL,
	`model` text NOT NULL,
	`model_version` text NOT NULL,
	`status` text NOT NULL,
	`page_count` integer NOT NULL,
	`confidence` real,
	`source_sha256` text NOT NULL,
	`artifact_key` text NOT NULL,
	`classification_type` text NOT NULL,
	`classification_confidence` real NOT NULL,
	`classification_reason` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_document_extractions_document_created` ON `document_extractions` (`document_id`,`created_at`);--> statement-breakpoint
CREATE TABLE `fact_extraction_details` (
	`fact_id` text PRIMARY KEY NOT NULL,
	`raw_value` text NOT NULL,
	`raw_unit` text,
	`conversion_factor` real,
	FOREIGN KEY (`fact_id`) REFERENCES `facts`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `fact_source_spans` (
	`fact_id` text PRIMARY KEY NOT NULL,
	`extraction_id` text NOT NULL,
	`block_ids` text NOT NULL,
	`bbox` text,
	`confidence` real NOT NULL,
	FOREIGN KEY (`fact_id`) REFERENCES `facts`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`extraction_id`) REFERENCES `document_extractions`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_fact_source_spans_extraction` ON `fact_source_spans` (`extraction_id`);