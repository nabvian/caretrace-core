CREATE TABLE `document_clinical_dates` (
	`id` text PRIMARY KEY NOT NULL,
	`document_id` text NOT NULL,
	`value` text NOT NULL,
	`type` text NOT NULL,
	`precision` text NOT NULL,
	`source_page` integer NOT NULL,
	`source_text` text NOT NULL,
	`confidence` text NOT NULL,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_document_clinical_dates_document` ON `document_clinical_dates` (`document_id`);--> statement-breakpoint
CREATE INDEX `idx_document_clinical_dates_value_type` ON `document_clinical_dates` (`value`,`type`);--> statement-breakpoint
CREATE TABLE `fact_observation_details` (
	`fact_id` text PRIMARY KEY NOT NULL,
	`reference_low` real,
	`reference_high` real,
	`reference_text` text,
	`specimen` text,
	`unit_status` text NOT NULL,
	`extraction_method` text NOT NULL,
	FOREIGN KEY (`fact_id`) REFERENCES `facts`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `fact_temporal` (
	`fact_id` text PRIMARY KEY NOT NULL,
	`event_date` text,
	`date_type` text,
	`precision` text,
	`status` text NOT NULL,
	`source_page` integer,
	`source_text` text,
	`confidence` text,
	FOREIGN KEY (`fact_id`) REFERENCES `facts`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_fact_temporal_date_type` ON `fact_temporal` (`event_date`,`date_type`);