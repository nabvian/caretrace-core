CREATE TABLE `terminology_release_governance` (
	`release_id` text PRIMARY KEY NOT NULL,
	`license_name` text NOT NULL,
	`license_status` text NOT NULL,
	`accepted_at` text NOT NULL,
	FOREIGN KEY (`release_id`) REFERENCES `terminology_releases`(`id`) ON UPDATE no action ON DELETE cascade
);
