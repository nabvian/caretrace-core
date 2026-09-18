-- CARETRACE relational schema.
-- All primary keys are UUIDs. Document filenames are NEVER used as keys.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cases (
    id            TEXT PRIMARY KEY,
    case_ref      TEXT NOT NULL UNIQUE,
    subject_label TEXT NOT NULL,
    subject_dob   TEXT,
    is_synthetic  INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id                TEXT PRIMARY KEY,
    case_id           TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    filename          TEXT NOT NULL,
    doc_type          TEXT NOT NULL DEFAULT 'OTHER',
    doc_date          TEXT,
    page_count        INTEGER NOT NULL DEFAULT 0,
    byte_size         INTEGER NOT NULL DEFAULT 0,
    sha256            TEXT,
    stored_path       TEXT,
    upload_status     TEXT NOT NULL DEFAULT 'UPLOADED',
    processing_status TEXT NOT NULL DEFAULT 'PENDING',
    processing_note   TEXT,
    ordinal           INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_id);

CREATE TABLE IF NOT EXISTS document_pages (
    id          TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    text        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pages_doc ON document_pages(document_id);

-- Provenance anchor. Every evidence row points at exactly one source row.
CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id     TEXT NOT NULL REFERENCES document_pages(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    source_text TEXT NOT NULL,
    char_start  INTEGER,
    char_end    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sources_case ON sources(case_id);

CREATE TABLE IF NOT EXISTS facts (
    id             TEXT PRIMARY KEY,
    case_id        TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    display_id     TEXT NOT NULL,
    evidence_type  TEXT NOT NULL DEFAULT 'OBSERVATION',
    concept        TEXT NOT NULL,          -- normalized concept key
    surface_form   TEXT NOT NULL,          -- wording as written in the document
    value_num      REAL,
    value_text     TEXT,
    -- For qualitative findings: the pack's mutually-exclusive value class key.
    -- Two facts sharing a concept but differing on value_key are documented
    -- disagreements; two sharing a value_key are the same finding worded
    -- differently. NULL for numeric observations.
    value_key      TEXT,
    unit           TEXT,
    obs_date       TEXT,
    date_precision TEXT NOT NULL DEFAULT 'day',
    source_id      TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    confidence     REAL NOT NULL DEFAULT 1.0,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_case ON facts(case_id);
CREATE INDEX IF NOT EXISTS idx_facts_concept ON facts(case_id, concept);

CREATE TABLE IF NOT EXISTS claims (
    id              TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    display_id      TEXT NOT NULL,
    claim_text      TEXT NOT NULL,
    claim_type      TEXT NOT NULL DEFAULT 'UNMAPPED',
    claim_date      TEXT,
    date_precision  TEXT NOT NULL DEFAULT 'day',
    source_id       TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    confidence      REAL NOT NULL DEFAULT 1.0,
    evidence_status TEXT NOT NULL DEFAULT 'NOT_ASSESSED',
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_case ON claims(case_id);

CREATE TABLE IF NOT EXISTS medications (
    id           TEXT PRIMARY KEY,
    case_id      TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    display_id   TEXT NOT NULL,
    drug_name    TEXT NOT NULL,           -- as written
    drug_norm    TEXT NOT NULL,           -- normalized key
    dose         REAL,
    unit         TEXT,
    frequency    TEXT,
    route        TEXT,
    status       TEXT NOT NULL DEFAULT 'DOCUMENTED',
    start_date   TEXT,
    stop_date    TEXT,
    record_date  TEXT,
    source_id    TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    confidence   REAL NOT NULL DEFAULT 1.0,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meds_case ON medications(case_id);

CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    display_id  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    label       TEXT NOT NULL,
    event_date  TEXT,
    detail      TEXT,
    payload     TEXT,
    source_id   TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_case ON events(case_id);

-- Documents mentioned inside other documents (resolved or not).
CREATE TABLE IF NOT EXISTS document_references (
    id            TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    display_id    TEXT NOT NULL,
    label         TEXT NOT NULL,
    doc_type_hint TEXT,
    source_id     TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    resolved_document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'UNRESOLVED',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    id         TEXT PRIMARY KEY,
    case_id    TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    rel_type   TEXT NOT NULL,
    from_type  TEXT NOT NULL,
    from_id    TEXT NOT NULL,
    to_type    TEXT NOT NULL,
    to_id      TEXT NOT NULL,
    detail     TEXT,
    status     TEXT NOT NULL DEFAULT 'DOCUMENTED',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rel_case ON relationships(case_id);
CREATE INDEX IF NOT EXISTS idx_rel_from ON relationships(case_id, from_id);

CREATE TABLE IF NOT EXISTS conflicts (
    id            TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    display_id    TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    concept       TEXT NOT NULL,
    concept_label TEXT NOT NULL,
    left_type     TEXT NOT NULL,
    left_id       TEXT NOT NULL,
    right_type    TEXT NOT NULL,
    right_id      TEXT NOT NULL,
    left_summary  TEXT NOT NULL,
    right_summary TEXT NOT NULL,
    -- Every record on each side of the disagreement, as a JSON array of ids.
    -- left_id/right_id are the representatives used for display; the member
    -- lists carry the full provenance so no supporting document is dropped.
    left_member_ids  TEXT NOT NULL DEFAULT '[]',
    right_member_ids TEXT NOT NULL DEFAULT '[]',
    delta         TEXT,
    basis         TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'UNRESOLVED',
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conflicts_case ON conflicts(case_id);

CREATE TABLE IF NOT EXISTS evidence_gaps (
    id                   TEXT PRIMARY KEY,
    case_id              TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    display_id           TEXT NOT NULL,
    gap_type             TEXT NOT NULL,
    subject_type         TEXT NOT NULL,
    subject_id           TEXT,
    title                TEXT NOT NULL,
    evidence_located     TEXT,   -- JSON array
    evidence_not_located TEXT,   -- JSON array
    basis                TEXT NOT NULL,
    status               TEXT NOT NULL,
    created_at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gaps_case ON evidence_gaps(case_id);

CREATE TABLE IF NOT EXISTS changes (
    id            TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    display_id    TEXT NOT NULL,
    concept       TEXT NOT NULL,
    concept_label TEXT NOT NULL,
    unit          TEXT,
    from_fact_id  TEXT NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    to_fact_id    TEXT NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    from_date     TEXT,
    to_date       TEXT,
    from_value    REAL,
    to_value      REAL,
    delta         REAL,
    direction     TEXT NOT NULL,
    basis         TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_case ON changes(case_id);

-- The immutable raw-text layer.
--
-- Write-once record of exactly what the parser saw, before any normalization,
-- terminology resolution or audit logic touches it. Downstream stages READ
-- this table and write elsewhere; nothing in the pipeline updates a row here.
-- That is what makes the original wording always recoverable, and it is the
-- anchor every provenance claim in the product ultimately resolves to.
CREATE TABLE IF NOT EXISTS raw_extractions (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    text_sha256     TEXT NOT NULL,
    char_count      INTEGER NOT NULL DEFAULT 0,
    page_offsets    TEXT NOT NULL DEFAULT '[]',
    method          TEXT NOT NULL,
    tool_name       TEXT,
    tool_version    TEXT,
    confidence      REAL,
    has_text_layer  INTEGER NOT NULL DEFAULT 1,
    note            TEXT,
    sidecar_path    TEXT,
    created_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_doc ON raw_extractions(document_id);

CREATE TABLE IF NOT EXISTS processing_runs (
    id          TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'RUNNING',
    stages      TEXT NOT NULL DEFAULT '[]',
    engine_version TEXT NOT NULL DEFAULT '0'
);
CREATE INDEX IF NOT EXISTS idx_runs_case ON processing_runs(case_id);

-- Terminology codings: advisory vocabulary annotations on facts, medications
-- and claims. Kept in their own table, never as columns on the annotated row,
-- because a coding is an OPINION OF AN EXTERNAL SERVICE about a phrase, while a
-- fact is what a document said. One phrase may carry codes from several
-- vocabularies, or none, and a re-resolution against a newer vocabulary
-- release must not rewrite the record of what the document stated.
--
-- No audit query reads this table. Conflict, change and gap detection use pack
-- concepts, so a terminology outage cannot alter an audit result.
CREATE TABLE IF NOT EXISTS codings (
    id TEXT PRIMARY KEY,
    -- CASCADE like every other case-scoped table: deleting a case must delete
    -- its annotations too, or the spec's deletion guarantee cannot be honoured.
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    -- What is being coded: 'fact' | 'medication' | 'claim'
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    system TEXT NOT NULL,
    system_uri TEXT,
    code TEXT NOT NULL,
    display TEXT,
    -- The phrase as the document wrote it, preserved verbatim.
    queried_text TEXT NOT NULL,
    match_kind TEXT NOT NULL,      -- EXACT | SYNONYM | APPROXIMATE | NONE
    -- 1 only for EXACT/SYNONYM. An APPROXIMATE coding is a suggestion for a
    -- reviewer and must never be read as an identity claim.
    assertable INTEGER NOT NULL DEFAULT 0,
    score REAL,
    version TEXT,                  -- vocabulary release, when reported
    provider_key TEXT NOT NULL,
    resolved_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_codings_case ON codings(case_id);
CREATE INDEX IF NOT EXISTS idx_codings_subject ON codings(subject_type, subject_id);

-- Cache of provider answers, keyed by (provider, vocabulary kind, phrase).
-- Two purposes: it makes re-processing a case cheap, and it lets a deployment
-- run fully offline against phrases already seen. `miss` records that a
-- provider searched and found nothing, so a known-absent phrase is not
-- re-queried on every run.
CREATE TABLE IF NOT EXISTS terminology_cache (
    id TEXT PRIMARY KEY,
    provider_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    query_norm TEXT NOT NULL,      -- casefolded, whitespace-collapsed phrase
    payload TEXT NOT NULL,         -- JSON list of coding dicts
    miss INTEGER NOT NULL DEFAULT 0,
    provider_version TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_termcache_key
    ON terminology_cache(provider_key, kind, query_norm);

-- ===========================================================================
-- Patient registry and the link graph.
--
-- Patients are DISCOVERED from documents, not declared: every document states
-- who it is about, and that assertion is recorded verbatim before any
-- resolution happens. The distinction matters for the same reason the fact /
-- claim distinction does -- what a document said is evidence; who the system
-- thinks it refers to is an inference, and the two must never be conflated.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS patients (
    id            TEXT PRIMARY KEY,
    -- Registry-assigned, human-readable. Never a clinical identifier.
    patient_ref   TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    -- Normalised for matching only; display_name keeps the documented form.
    name_key      TEXT NOT NULL,
    dob           TEXT,
    sex           TEXT,
    mrn           TEXT,
    is_synthetic  INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_patients_mrn ON patients(mrn);
CREATE INDEX IF NOT EXISTS idx_patients_key ON patients(name_key, dob);

-- What one document ASSERTED about identity, retained verbatim. This is
-- evidence and is never rewritten by resolution; a corrected spelling lives on
-- the patient row, never here.
CREATE TABLE IF NOT EXISTS identity_assertions (
    id           TEXT PRIMARY KEY,
    case_id      TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_id    TEXT REFERENCES sources(id) ON DELETE SET NULL,
    raw_name     TEXT,
    raw_dob      TEXT,
    raw_sex      TEXT,
    raw_mrn      TEXT,
    name_key     TEXT,
    dob          TEXT,
    sex          TEXT,
    mrn          TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_idassert_doc ON identity_assertions(document_id);

-- The resolution decision for one assertion. A link is never implicit: either
-- a row says which patient a document was attached to and on what basis, or
-- the document is unlinked and says why.
CREATE TABLE IF NOT EXISTS identity_links (
    id            TEXT PRIMARY KEY,
    assertion_id  TEXT NOT NULL REFERENCES identity_assertions(id) ON DELETE CASCADE,
    case_id       TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    document_id   TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    -- NULL while a decision is pending review. A null patient_id is the
    -- system refusing to guess, which is the intended outcome, not a failure.
    patient_id    TEXT REFERENCES patients(id) ON DELETE CASCADE,
    -- LINKED | NEEDS_REVIEW | NEW_PATIENT
    status        TEXT NOT NULL,
    -- MRN_EXACT | NAME_DOB_SEX | NO_MATCH | ...
    basis         TEXT NOT NULL,
    -- Why, in the product's own language. Rendered to the reviewer verbatim.
    rationale     TEXT NOT NULL,
    -- Candidates considered but not chosen, as JSON. Present for every
    -- NEEDS_REVIEW row so a reviewer sees what the system was choosing between.
    candidates    TEXT,
    resolved_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_idlink_status ON identity_links(status);
CREATE INDEX IF NOT EXISTS idx_idlink_case ON identity_links(case_id);

-- Institutions and clinicians, also discovered from documents.
CREATE TABLE IF NOT EXISTS institutions (
    id           TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    name_key     TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clinicians (
    id             TEXT PRIMARY KEY,
    display_name   TEXT NOT NULL,
    name_key       TEXT NOT NULL,
    institution_id TEXT REFERENCES institutions(id) ON DELETE SET NULL,
    created_at     TEXT NOT NULL,
    UNIQUE (name_key, institution_id)
);

-- Who did what on a document. Roles are documented, never inferred from
-- position on the page.
CREATE TABLE IF NOT EXISTS document_participants (
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    clinician_id TEXT REFERENCES clinicians(id) ON DELETE CASCADE,
    -- ORDERING | PERFORMING | AUTHORING | REFERRING
    role         TEXT NOT NULL,
    source_id    TEXT REFERENCES sources(id) ON DELETE SET NULL,
    raw_text     TEXT,
    UNIQUE (document_id, clinician_id, role)
);
CREATE INDEX IF NOT EXISTS idx_docpart_doc ON document_participants(document_id);

-- An encounter groups documents by patient and date. Derived, and rebuilt on
-- every run like every other derived table.
CREATE TABLE IF NOT EXISTS encounters (
    id             TEXT PRIMARY KEY,
    case_id        TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    patient_id     TEXT REFERENCES patients(id) ON DELETE CASCADE,
    occurred_on    TEXT,
    kind           TEXT NOT NULL DEFAULT 'DOCUMENTED_CONTACT',
    institution_id TEXT REFERENCES institutions(id) ON DELETE SET NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_encounter_patient ON encounters(patient_id);

CREATE TABLE IF NOT EXISTS encounter_documents (
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    PRIMARY KEY (encounter_id, document_id)
);

-- --------------------------------------------------------------------------
-- Bulk ingestion
--
-- A job is durable so that an interrupted batch can be resumed rather than
-- restarted: items carry their own terminal status, written in the same
-- transaction as the document rows they produced. An item still PENDING after
-- a crash was, by construction, never committed, so re-running the job is
-- safe and idempotent.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id           TEXT PRIMARY KEY,
    case_id      TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    source       TEXT NOT NULL,
    -- PENDING | RUNNING | COMPLETED | INTERRUPTED
    status       TEXT NOT NULL DEFAULT 'PENDING',
    total        INTEGER NOT NULL DEFAULT 0,
    worker_count INTEGER NOT NULL DEFAULT 1,
    chunk_size   INTEGER NOT NULL DEFAULT 200,
    started_at   TEXT,
    finished_at  TEXT,
    note         TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_items (
    id           TEXT PRIMARY KEY,
    job_id       TEXT NOT NULL REFERENCES ingest_jobs(id) ON DELETE CASCADE,
    path         TEXT NOT NULL,
    display_name TEXT NOT NULL,
    ordinal      INTEGER NOT NULL,
    -- PENDING | INGESTED | DUPLICATE | FAILED
    status       TEXT NOT NULL DEFAULT 'PENDING',
    sha256       TEXT,
    document_id  TEXT REFERENCES documents(id) ON DELETE SET NULL,
    duplicate_of TEXT,
    error        TEXT,
    parse_ms     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ingest_items_job
    ON ingest_items(job_id, status);
