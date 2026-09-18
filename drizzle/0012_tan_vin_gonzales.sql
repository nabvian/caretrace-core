CREATE TABLE `evidence_terminology_candidates` (
	`id` text PRIMARY KEY NOT NULL,
	`case_id` text NOT NULL,
	`subject_type` text NOT NULL,
	`subject_id` text NOT NULL,
	`source_system` text NOT NULL,
	`source_code` text NOT NULL,
	`source_version` text NOT NULL,
	`source_uri` text NOT NULL,
	`label` text NOT NULL,
	`semantic_type` text,
	`units` text NOT NULL,
	`status` text NOT NULL,
	`reason` text NOT NULL,
	`resolved_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_evidence_terminology_candidate_unique` ON `evidence_terminology_candidates` (`subject_type`,`subject_id`,`source_system`,`source_code`,`source_version`);--> statement-breakpoint
CREATE INDEX `idx_evidence_terminology_candidates_case_subject` ON `evidence_terminology_candidates` (`case_id`,`subject_type`,`subject_id`);--> statement-breakpoint
CREATE TABLE `patient_search_index` (
	`case_id` text PRIMARY KEY NOT NULL,
	`organization_id` text NOT NULL,
	`patient_name_normalized` text NOT NULL,
	`case_code_normalized` text NOT NULL,
	`dob_normalized` text NOT NULL,
	`contact_normalized` text NOT NULL,
	`email_normalized` text NOT NULL,
	`external_identifiers_normalized` text NOT NULL,
	`search_text` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`case_id`) REFERENCES `cases`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`organization_id`) REFERENCES `hospital_organizations`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_patient_search_name` ON `patient_search_index` (`organization_id`,`patient_name_normalized`);--> statement-breakpoint
CREATE INDEX `idx_patient_search_case_code` ON `patient_search_index` (`organization_id`,`case_code_normalized`);--> statement-breakpoint
CREATE INDEX `idx_patient_search_contact` ON `patient_search_index` (`organization_id`,`contact_normalized`);--> statement-breakpoint
CREATE INDEX `idx_patient_search_email` ON `patient_search_index` (`organization_id`,`email_normalized`);--> statement-breakpoint
ALTER TABLE `cases` ADD `lifecycle_state` text DEFAULT 'EMPTY' NOT NULL;--> statement-breakpoint
ALTER TABLE `cases` ADD `lifecycle_updated_at` text DEFAULT '' NOT NULL;--> statement-breakpoint
CREATE INDEX `idx_cases_organization_lifecycle` ON `cases` (`organization_id`,`lifecycle_state`,`updated_at`);--> statement-breakpoint
UPDATE `cases` SET
  `lifecycle_state` = CASE
    WHEN EXISTS (SELECT 1 FROM `processing_runs` r WHERE r.case_id=`cases`.id AND r.status='RUNNING') THEN 'AUDITING'
    WHEN EXISTS (SELECT 1 FROM `processing_runs` r WHERE r.case_id=`cases`.id AND r.is_current=1 AND r.status='REQUIRES_REVIEW') THEN 'REVIEW_REQUIRED'
    WHEN EXISTS (SELECT 1 FROM `processing_runs` r WHERE r.case_id=`cases`.id AND r.is_current=1 AND r.status='COMPLETED') THEN 'AUDITED'
    WHEN EXISTS (SELECT 1 FROM `processing_runs` r WHERE r.case_id=`cases`.id AND r.status='FAILED') THEN 'FAILED'
    WHEN EXISTS (SELECT 1 FROM `documents` d WHERE d.case_id=`cases`.id) THEN 'AUDIT_REQUIRED'
    ELSE 'EMPTY'
  END,
  `lifecycle_updated_at` = `updated_at`;--> statement-breakpoint
INSERT INTO `patient_search_index` (`case_id`,`organization_id`,`patient_name_normalized`,`case_code_normalized`,`dob_normalized`,`contact_normalized`,`email_normalized`,`external_identifiers_normalized`,`search_text`,`updated_at`)
SELECT c.id,c.organization_id,lower(c.patient_label),lower(c.case_code),lower(coalesce(c.dob,'')),lower(coalesce(c.contact_number,'')),lower(coalesce(c.email,'')),
  lower(coalesce((SELECT group_concat(p.system || ' ' || p.value,' ') FROM patient_external_identifiers p WHERE p.case_id=c.id),'')),
  lower(trim(c.patient_label || ' ' || c.case_code || ' ' || coalesce(c.dob,'') || ' ' || coalesce(c.contact_number,'') || ' ' || coalesce(c.email,'') || ' ' || coalesce((SELECT group_concat(p.system || ' ' || p.value,' ') FROM patient_external_identifiers p WHERE p.case_id=c.id),''))),c.updated_at
FROM cases c WHERE c.organization_id IS NOT NULL;
