CREATE TABLE `claim_rule_bindings` (
	`claim_id` text PRIMARY KEY NOT NULL,
	`claim_type` text,
	`support_concepts` text,
	`gap_rule` text,
	`referenced_document` text,
	`expected_concept` text,
	`lookback_days` integer,
	`evidence_labels` text,
	FOREIGN KEY (`claim_id`) REFERENCES `claims`(`id`) ON UPDATE no action ON DELETE cascade
);
