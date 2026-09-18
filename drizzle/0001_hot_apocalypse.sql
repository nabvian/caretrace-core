CREATE TABLE `terminology_aliases` (
	`id` text PRIMARY KEY NOT NULL,
	`concept_id` text NOT NULL,
	`alias` text NOT NULL,
	`normalized_alias` text NOT NULL,
	FOREIGN KEY (`concept_id`) REFERENCES `terminology_concepts`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_term_alias_normalized` ON `terminology_aliases` (`normalized_alias`);--> statement-breakpoint
CREATE INDEX `idx_term_alias_concept` ON `terminology_aliases` (`concept_id`);--> statement-breakpoint
CREATE TABLE `terminology_api_cache` (
	`id` text PRIMARY KEY NOT NULL,
	`source_key` text NOT NULL,
	`cache_key` text NOT NULL,
	`response` text NOT NULL,
	`expires_at` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_term_cache_source_key` ON `terminology_api_cache` (`source_key`,`cache_key`);--> statement-breakpoint
CREATE INDEX `idx_term_cache_expiry` ON `terminology_api_cache` (`expires_at`);--> statement-breakpoint
CREATE TABLE `terminology_concepts` (
	`id` text PRIMARY KEY NOT NULL,
	`release_id` text NOT NULL,
	`caretrace_id` text NOT NULL,
	`source_system` text NOT NULL,
	`source_code` text NOT NULL,
	`source_version` text NOT NULL,
	`source_uri` text NOT NULL,
	`source_label` text NOT NULL,
	`label` text NOT NULL,
	`normalized_label` text NOT NULL,
	`domain` text NOT NULL,
	`category` text NOT NULL,
	`semantic_type` text NOT NULL,
	`status` text NOT NULL,
	`imported_at` text NOT NULL,
	FOREIGN KEY (`release_id`) REFERENCES `terminology_releases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_term_concept_release_code` ON `terminology_concepts` (`release_id`,`source_code`);--> statement-breakpoint
CREATE INDEX `idx_term_concept_caretrace` ON `terminology_concepts` (`caretrace_id`);--> statement-breakpoint
CREATE INDEX `idx_term_concept_label` ON `terminology_concepts` (`normalized_label`);--> statement-breakpoint
CREATE TABLE `terminology_imports` (
	`id` text PRIMARY KEY NOT NULL,
	`release_id` text,
	`source_key` text NOT NULL,
	`filename` text NOT NULL,
	`status` text NOT NULL,
	`report` text NOT NULL,
	`started_at` text NOT NULL,
	`completed_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_term_import_source_status` ON `terminology_imports` (`source_key`,`status`);--> statement-breakpoint
CREATE TABLE `terminology_mappings` (
	`id` text PRIMARY KEY NOT NULL,
	`concept_id` text NOT NULL,
	`system` text NOT NULL,
	`code` text,
	`source_version` text NOT NULL,
	`source_uri` text NOT NULL,
	`relationship` text NOT NULL,
	`status` text NOT NULL,
	FOREIGN KEY (`concept_id`) REFERENCES `terminology_concepts`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_term_mapping_concept` ON `terminology_mappings` (`concept_id`);--> statement-breakpoint
CREATE INDEX `idx_term_mapping_system_code` ON `terminology_mappings` (`system`,`code`);--> statement-breakpoint
CREATE TABLE `terminology_relationships` (
	`id` text PRIMARY KEY NOT NULL,
	`concept_id` text NOT NULL,
	`type` text NOT NULL,
	`target_source_code` text NOT NULL,
	`relationship_group` text,
	`active` integer NOT NULL,
	FOREIGN KEY (`concept_id`) REFERENCES `terminology_concepts`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_term_relationship_concept` ON `terminology_relationships` (`concept_id`);--> statement-breakpoint
CREATE INDEX `idx_term_relationship_target` ON `terminology_relationships` (`target_source_code`);--> statement-breakpoint
CREATE TABLE `terminology_releases` (
	`id` text PRIMARY KEY NOT NULL,
	`source_key` text NOT NULL,
	`version` text NOT NULL,
	`release_date` text NOT NULL,
	`import_date` text NOT NULL,
	`status` text NOT NULL,
	`format` text NOT NULL,
	`checksum_algorithm` text NOT NULL,
	`checksum_expected` text,
	`checksum_actual` text,
	`checksum_verified` integer,
	`record_count` integer NOT NULL,
	`artifact_key` text,
	`previous_release_id` text,
	FOREIGN KEY (`source_key`) REFERENCES `terminology_sources`(`key`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `idx_term_release_source_status` ON `terminology_releases` (`source_key`,`status`);--> statement-breakpoint
CREATE INDEX `idx_term_release_source_version` ON `terminology_releases` (`source_key`,`version`);--> statement-breakpoint
CREATE TABLE `terminology_sources` (
	`key` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`source_uri` text NOT NULL,
	`license_status` text NOT NULL,
	`api_configured` integer DEFAULT false NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `terminology_units` (
	`id` text PRIMARY KEY NOT NULL,
	`concept_id` text NOT NULL,
	`unit` text NOT NULL,
	FOREIGN KEY (`concept_id`) REFERENCES `terminology_concepts`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_term_unit_concept` ON `terminology_units` (`concept_id`);
--> statement-breakpoint
PRAGMA optimize;
