CREATE TABLE `actor_audit_events` (
	`id` text PRIMARY KEY NOT NULL,
	`organization_id` text NOT NULL,
	`actor_user_id` text NOT NULL,
	`actor_email` text NOT NULL,
	`actor_display_name` text,
	`actor_role` text NOT NULL CHECK (`actor_role` IN ('OWNER','ADMIN','CLINICIAN','REVIEWER','VIEWER')),
	`request_id` text NOT NULL,
	`action` text NOT NULL,
	`target_type` text NOT NULL,
	`target_id` text NOT NULL,
	`case_id` text,
	`metadata_json` text NOT NULL CHECK (json_valid(`metadata_json`)),
	`created_at` text NOT NULL,
	FOREIGN KEY (`organization_id`) REFERENCES `hospital_organizations`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE restrict
);
--> statement-breakpoint
CREATE INDEX `idx_actor_audit_org_time` ON `actor_audit_events` (`organization_id`,`created_at`,`id`);--> statement-breakpoint
CREATE INDEX `idx_actor_audit_case_time` ON `actor_audit_events` (`organization_id`,`case_id`,`created_at`,`id`);--> statement-breakpoint
CREATE TRIGGER `actor_audit_events_no_update`
BEFORE UPDATE ON `actor_audit_events`
BEGIN
  SELECT RAISE(ABORT,'actor_audit_events are append-only');
END;--> statement-breakpoint
CREATE TRIGGER `actor_audit_events_no_delete`
BEFORE DELETE ON `actor_audit_events`
BEGIN
  SELECT RAISE(ABORT,'actor_audit_events are append-only');
END;--> statement-breakpoint
CREATE TABLE `hospital_bootstrap` (
	`id` text PRIMARY KEY NOT NULL,
	`organization_id` text NOT NULL,
	`owner_user_id` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`organization_id`) REFERENCES `hospital_organizations`(`id`) ON UPDATE no action ON DELETE restrict
);
--> statement-breakpoint
CREATE TABLE `hospital_memberships` (
	`id` text PRIMARY KEY NOT NULL,
	`organization_id` text NOT NULL,
	`user_id` text,
	`email` text NOT NULL,
	`display_name` text,
	`role` text NOT NULL CHECK (`role` IN ('OWNER','ADMIN','CLINICIAN','REVIEWER','VIEWER')),
	`status` text NOT NULL CHECK (`status` IN ('INVITED','ACTIVE','SUSPENDED')),
	`invited_by_user_id` text,
	`created_at` text NOT NULL,
	`claimed_at` text,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`organization_id`) REFERENCES `hospital_organizations`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_hospital_memberships_org_email` ON `hospital_memberships` (`organization_id`,`email`);--> statement-breakpoint
CREATE UNIQUE INDEX `idx_hospital_memberships_org_user` ON `hospital_memberships` (`organization_id`,`user_id`);--> statement-breakpoint
CREATE INDEX `idx_hospital_memberships_user` ON `hospital_memberships` (`user_id`,`status`,`organization_id`);--> statement-breakpoint
CREATE INDEX `idx_hospital_memberships_invite` ON `hospital_memberships` (`email`,`status`,`organization_id`);--> statement-breakpoint
CREATE TABLE `hospital_organizations` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `interoperability_import_analyses` (
	`id` text PRIMARY KEY NOT NULL,
	`organization_id` text NOT NULL,
	`source_format` text NOT NULL CHECK (`source_format` IN ('FHIR_R4','HL7_V2_ORU_R01')),
	`source_sha256` text NOT NULL CHECK (length(`source_sha256`)=64),
	`source_object_key` text NOT NULL,
	`canonical_object_key` text NOT NULL,
	`semantic_summary_json` text NOT NULL CHECK (json_valid(`semantic_summary_json`)),
	`actor_user_id` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`organization_id`) REFERENCES `hospital_organizations`(`id`) ON UPDATE no action ON DELETE restrict
);
--> statement-breakpoint
CREATE INDEX `idx_import_analyses_org_time` ON `interoperability_import_analyses` (`organization_id`,`created_at`,`id`);--> statement-breakpoint
CREATE TRIGGER `interoperability_import_analyses_no_update`
BEFORE UPDATE ON `interoperability_import_analyses`
BEGIN
  SELECT RAISE(ABORT,'interoperability_import_analyses are immutable');
END;--> statement-breakpoint
CREATE TRIGGER `interoperability_import_analyses_no_delete`
BEFORE DELETE ON `interoperability_import_analyses`
BEGIN
  SELECT RAISE(ABORT,'interoperability_import_analyses are immutable');
END;--> statement-breakpoint
CREATE TABLE `interoperability_transformations` (
	`id` text PRIMARY KEY NOT NULL,
	`organization_id` text NOT NULL,
	`case_id` text NOT NULL,
	`source_run_id` text,
	`target` text NOT NULL CHECK (`target` IN ('FHIR_R4','HL7_V2_ORU_R01')),
	`profile` text NOT NULL,
	`media_type` text NOT NULL,
	`artifact_object_key` text NOT NULL,
	`artifact_sha256` text NOT NULL CHECK (length(`artifact_sha256`)=64),
	`validation_json` text NOT NULL CHECK (json_valid(`validation_json`)),
	`semantic_summary_json` text NOT NULL CHECK (json_valid(`semantic_summary_json`)),
	`actor_user_id` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`organization_id`) REFERENCES `hospital_organizations`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`source_run_id`) REFERENCES `processing_runs`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE INDEX `idx_transformations_case_time` ON `interoperability_transformations` (`organization_id`,`case_id`,`created_at`);--> statement-breakpoint
CREATE TRIGGER `interoperability_transformations_no_update`
BEFORE UPDATE ON `interoperability_transformations`
BEGIN
  SELECT RAISE(ABORT,'interoperability_transformations are immutable');
END;--> statement-breakpoint
CREATE TRIGGER `interoperability_transformations_no_delete`
BEFORE DELETE ON `interoperability_transformations`
BEGIN
  SELECT RAISE(ABORT,'interoperability_transformations are immutable');
END;--> statement-breakpoint
CREATE TABLE `semantic_integrity_findings` (
	`id` text PRIMARY KEY NOT NULL,
	`transformation_id` text NOT NULL,
	`source_path` text NOT NULL,
	`target_path` text,
	`status` text NOT NULL CHECK (`status` IN ('PRESERVED','TRANSFORMED','UNRESOLVED','LOST')),
	`severity` text NOT NULL CHECK (`severity` IN ('INFO','MODERATE','HIGH')),
	`reason` text,
	`created_at` text NOT NULL,
	FOREIGN KEY (`transformation_id`) REFERENCES `interoperability_transformations`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_semantic_findings_status` ON `semantic_integrity_findings` (`transformation_id`,`status`,`severity`);--> statement-breakpoint
DROP INDEX `idx_patient_external_identifier_system_value`;--> statement-breakpoint
ALTER TABLE `patient_external_identifiers` ADD `organization_id` text REFERENCES hospital_organizations(id);--> statement-breakpoint
CREATE UNIQUE INDEX `idx_patient_external_identifier_org_system_value` ON `patient_external_identifiers` (`organization_id`,`system`,`value`);--> statement-breakpoint
CREATE INDEX `idx_patient_external_identifier_system_value_lookup` ON `patient_external_identifiers` (`system`,`value`);--> statement-breakpoint
ALTER TABLE `bulk_ingestions` ADD `organization_id` text REFERENCES hospital_organizations(id);--> statement-breakpoint
CREATE INDEX `idx_bulk_ingestions_organization` ON `bulk_ingestions` (`organization_id`,`updated_at`,`id`);--> statement-breakpoint
ALTER TABLE `cases` ADD `organization_id` text REFERENCES hospital_organizations(id);--> statement-breakpoint
CREATE INDEX `idx_cases_organization_updated` ON `cases` (`organization_id`,`updated_at`,`id`);
