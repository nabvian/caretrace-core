"""Domain model for CARETRACE.

Deliberately domain-independent at the core: a Fact is a normalized concept, a
value, a date and a Source. Medical meaning lives in packs/medical, not here.

Vocabulary note: nothing in this module asserts truth. `status` fields carry
documentation states (DOCUMENTED / UNRESOLVED / MISSING), never clinical
judgements.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Enumerations (plain string constants — inspectable, serializable)
# --------------------------------------------------------------------------

class DocType:
    LAB_REPORT = "LAB_REPORT"
    PRESCRIPTION = "PRESCRIPTION"
    CONSULTATION = "CONSULTATION"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    MEDICATION_LIST = "MEDICATION_LIST"
    REFERRAL = "REFERRAL"
    FOLLOWUP = "FOLLOWUP"
    IMAGING_REPORT = "IMAGING_REPORT"
    PATHOLOGY_REPORT = "PATHOLOGY_REPORT"
    ECG_REPORT = "ECG_REPORT"
    EEG_REPORT = "EEG_REPORT"
    MOLECULAR_REPORT = "MOLECULAR_REPORT"
    OTHER = "OTHER"

    ALL = [LAB_REPORT, PRESCRIPTION, CONSULTATION, DISCHARGE_SUMMARY,
           MEDICATION_LIST, REFERRAL, FOLLOWUP, IMAGING_REPORT,
           PATHOLOGY_REPORT, ECG_REPORT, EEG_REPORT, MOLECULAR_REPORT,
           OTHER]

    LABELS = {
        LAB_REPORT: "Laboratory Report",
        PRESCRIPTION: "Prescription",
        CONSULTATION: "Consultation Note",
        DISCHARGE_SUMMARY: "Discharge Summary",
        MEDICATION_LIST: "Medication List",
        REFERRAL: "Referral Letter",
        FOLLOWUP: "Follow-up Note",
        IMAGING_REPORT: "Imaging Report",
        PATHOLOGY_REPORT: "Pathology Report",
        ECG_REPORT: "ECG Report",
        EEG_REPORT: "EEG Report",
        MOLECULAR_REPORT: "Molecular Diagnostics Report",
        OTHER: "Other Document",
    }


class EvidenceType:
    OBSERVATION = "OBSERVATION"
    CLAIM = "CLAIM"
    MEDICATION = "MEDICATION"
    PROCEDURE = "PROCEDURE"
    DIAGNOSIS_STATEMENT = "DIAGNOSIS_STATEMENT"
    DOCUMENT_EVENT = "DOCUMENT_EVENT"


class RelType:
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    MENTIONS = "MENTIONS"
    DUPLICATES = "DUPLICATES"
    SUPERSEDES = "SUPERSEDES"
    PRECEDES = "PRECEDES"
    FOLLOWS = "FOLLOWS"
    SAME_CONCEPT = "SAME_CONCEPT"
    CHANGED_FROM = "CHANGED_FROM"
    CHANGED_TO = "CHANGED_TO"
    MISSING_SUPPORT = "MISSING_SUPPORT"
    REFERENCES = "REFERENCES"

    ALL = [SUPPORTS, CONTRADICTS, MENTIONS, DUPLICATES, SUPERSEDES, PRECEDES,
           FOLLOWS, SAME_CONCEPT, CHANGED_FROM, CHANGED_TO, MISSING_SUPPORT,
           REFERENCES]


class Status:
    VERIFIED = "VERIFIED"
    DOCUMENTED = "DOCUMENTED"
    CHANGED = "CHANGED"
    CONFLICT = "CONFLICT"
    MISSING = "MISSING"
    UNRESOLVED = "UNRESOLVED"


class ClaimEvidenceStatus:
    SUPPORTING_EVIDENCE = "SUPPORTING_EVIDENCE"
    CONTRADICTING_EVIDENCE = "CONTRADICTING_EVIDENCE"
    NO_LOCATED_EVIDENCE = "NO_LOCATED_EVIDENCE"
    NOT_ASSESSED = "NOT_ASSESSED"


class GapType:
    MISSING_SUPPORTING_TEST = "MISSING_SUPPORTING_TEST"
    MISSING_FOLLOWUP = "MISSING_FOLLOWUP"
    MEDICATION_DOCUMENTATION_GAP = "MEDICATION_DOCUMENTATION_GAP"
    MISSING_SOURCE = "MISSING_SOURCE"


class ConflictType:
    NUMERIC_OBSERVATION = "NUMERIC_OBSERVATION"
    MEDICATION_DOCUMENTATION = "MEDICATION_DOCUMENTATION"
    STATUS_STATEMENT = "STATUS_STATEMENT"


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------

@dataclass
class Case:
    case_ref: str
    subject_label: str
    subject_dob: Optional[str] = None
    is_synthetic: bool = True
    notes: str = ""
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Document:
    case_id: str
    filename: str
    doc_type: str = DocType.OTHER
    doc_date: Optional[str] = None
    page_count: int = 0
    byte_size: int = 0
    sha256: Optional[str] = None
    stored_path: Optional[str] = None
    upload_status: str = "UPLOADED"
    processing_status: str = "PENDING"
    processing_note: Optional[str] = None
    ordinal: int = 0
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class RawExtraction:
    """Write-once record of the complete text as the parser saw it.

    `page_offsets` holds [start, end) character offsets per page into `text`,
    so any downstream span can be resolved back to a page without re-parsing
    the original file. Nothing in the pipeline mutates an instance of this:
    normalization and terminology resolution read it and write elsewhere.
    """
    document_id: str
    text: str
    text_sha256: str
    char_count: int = 0
    page_offsets: str = "[]"          # JSON [[start, end], ...]
    method: str = "NONE"
    tool_name: Optional[str] = None
    tool_version: Optional[str] = None
    confidence: Optional[float] = None
    has_text_layer: int = 1
    note: Optional[str] = None
    sidecar_path: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


class ExtractionMethod:
    """How the raw text was obtained. Never guessed, always recorded."""
    PDF_TEXT_LAYER = "PDF_TEXT_LAYER"
    PLAIN_TEXT = "PLAIN_TEXT"
    OCR = "OCR"
    NONE = "NONE"


@dataclass
class DocumentPage:
    document_id: str
    page_number: int
    text: str
    id: str = field(default_factory=new_id)


@dataclass
class Source:
    """The provenance anchor: document + page + verbatim text span."""
    case_id: str
    document_id: str
    page_id: str
    page_number: int
    source_text: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    id: str = field(default_factory=new_id)


@dataclass
class Fact:
    case_id: str
    display_id: str
    concept: str
    surface_form: str
    source_id: str
    evidence_type: str = EvidenceType.OBSERVATION
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    # Mutually-exclusive value class for qualitative findings (see schema.sql).
    value_key: Optional[str] = None
    unit: Optional[str] = None
    obs_date: Optional[str] = None
    date_precision: str = "day"
    confidence: float = 1.0
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Claim:
    case_id: str
    display_id: str
    claim_text: str
    source_id: str
    claim_type: str = "UNMAPPED"
    claim_date: Optional[str] = None
    date_precision: str = "day"
    confidence: float = 1.0
    evidence_status: str = ClaimEvidenceStatus.NOT_ASSESSED
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Medication:
    case_id: str
    display_id: str
    drug_name: str
    drug_norm: str
    source_id: str
    dose: Optional[float] = None
    unit: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    status: str = "DOCUMENTED"
    start_date: Optional[str] = None
    stop_date: Optional[str] = None
    record_date: Optional[str] = None
    confidence: float = 1.0
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Event:
    case_id: str
    display_id: str
    event_type: str
    label: str
    source_id: str
    event_date: Optional[str] = None
    detail: Optional[str] = None
    payload: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class DocumentReference:
    case_id: str
    display_id: str
    label: str
    source_id: str
    doc_type_hint: Optional[str] = None
    resolved_document_id: Optional[str] = None
    status: str = "UNRESOLVED"
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Relationship:
    case_id: str
    rel_type: str
    from_type: str
    from_id: str
    to_type: str
    to_id: str
    detail: Optional[str] = None
    status: str = Status.DOCUMENTED
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Conflict:
    case_id: str
    display_id: str
    conflict_type: str
    concept: str
    concept_label: str
    left_type: str
    left_id: str
    right_type: str
    right_id: str
    left_summary: str
    right_summary: str
    #: Every record on each side of the disagreement. left_id/right_id are the
    #: display representatives; these lists preserve the full provenance so a
    #: value restated across several documents keeps all of its sources.
    left_member_ids: list[str]
    right_member_ids: list[str]
    basis: str
    delta: Optional[str] = None
    status: str = Status.UNRESOLVED
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class EvidenceGap:
    case_id: str
    display_id: str
    gap_type: str
    subject_type: str
    title: str
    basis: str
    status: str
    subject_id: Optional[str] = None
    evidence_located: list[str] = field(default_factory=list)
    evidence_not_located: list[str] = field(default_factory=list)
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Change:
    case_id: str
    display_id: str
    concept: str
    concept_label: str
    from_fact_id: str
    to_fact_id: str
    direction: str
    basis: str
    unit: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    from_value: Optional[float] = None
    to_value: Optional[float] = None
    delta: Optional[float] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class ProcessingRun:
    case_id: str
    engine_version: str
    stages: list[dict[str, Any]] = field(default_factory=list)
    status: str = "RUNNING"
    started_at: str = field(default_factory=now_iso)
    finished_at: Optional[str] = None
    id: str = field(default_factory=new_id)


def to_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)

@dataclass
class Coding:
    """A vocabulary code attached to a fact, medication or claim.

    Advisory metadata: it records that a phrase in a document plausibly denotes
    a published concept. The audit engine never reads it, so a terminology
    service being available or not cannot change an audit outcome.
    """
    case_id: str
    subject_type: str                 # 'fact' | 'medication' | 'claim'
    subject_id: str
    system: str
    code: str
    queried_text: str
    match_kind: str
    provider_key: str
    system_uri: Optional[str] = None
    display: Optional[str] = None
    # 1 only for EXACT/SYNONYM matches -- an approximate match is a suggestion.
    assertable: int = 0
    score: Optional[float] = None
    version: Optional[str] = None
    resolved_at: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class TerminologyCacheEntry:
    """One remembered provider answer, so re-processing costs no network call."""
    provider_key: str
    kind: str
    query_norm: str
    payload: str                      # JSON list of coding dicts
    miss: int = 0
    provider_version: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


class SubjectType:
    """What a coding can be attached to."""
    FACT = "fact"
    MEDICATION = "medication"
    CLAIM = "claim"
    ALL = (FACT, MEDICATION, CLAIM)


# ===========================================================================
# Patient registry and the link graph.
#
# Patients, institutions and clinicians are DURABLE: they outlive a processing
# run and span cases, because a registry that resets on re-processing cannot
# resolve identity across cases at all. Everything else here (assertions,
# links, encounters) is derived and rebuilt per run.
# ===========================================================================

@dataclass
class Patient:
    """A person the registry believes exists, assembled from documents.

    `display_name` is a documented form, kept for reading. `name_key` is the
    folded form, kept for matching. They are separate fields because the
    matching form is lossy on purpose and must never be shown as what a
    document said.
    """
    patient_ref: str
    display_name: str
    name_key: str
    dob: Optional[str] = None
    sex: Optional[str] = None
    mrn: Optional[str] = None
    is_synthetic: bool = True
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class IdentityAssertionRow:
    """Identity as one document stated it. Evidence, never rewritten."""
    case_id: str
    document_id: str
    source_id: Optional[str] = None
    raw_name: Optional[str] = None
    raw_dob: Optional[str] = None
    raw_sex: Optional[str] = None
    raw_mrn: Optional[str] = None
    name_key: Optional[str] = None
    dob: Optional[str] = None
    sex: Optional[str] = None
    mrn: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class IdentityLink:
    """The registry's decision about one assertion.

    A null `patient_id` with status NEEDS_REVIEW is the intended outcome for an
    ambiguous document, not a failure to process it.
    """
    case_id: str
    document_id: str
    assertion_id: str
    status: str                       # LINKED | NEEDS_REVIEW | NEW_PATIENT
    basis: str
    rationale: str
    patient_id: Optional[str] = None
    candidates: Optional[list] = None  # JSON: what was considered, not chosen
    id: str = field(default_factory=new_id)
    resolved_at: str = field(default_factory=now_iso)


@dataclass
class Institution:
    display_name: str
    name_key: str
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Clinician:
    display_name: str
    name_key: str
    institution_id: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class DocumentParticipant:
    """Who a document says did what. The role is read from the document's own
    label ("Requested by", "Verified by"), never inferred from page position."""
    document_id: str
    role: str                         # ORDERING | PERFORMING | AUTHORING | REFERRING
    clinician_id: Optional[str] = None
    source_id: Optional[str] = None
    raw_text: Optional[str] = None
    id: str = field(default_factory=new_id)


@dataclass
class Encounter:
    """Documents about one patient on one date, grouped.

    This is a documentary grouping, not a clinical visit: CARETRACE cannot know
    whether two reports on one date belong to one contact. The kind is named
    DOCUMENTED_CONTACT to keep that honest.
    """
    case_id: str
    patient_id: Optional[str] = None
    occurred_on: Optional[str] = None
    kind: str = "DOCUMENTED_CONTACT"
    institution_id: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


class ParticipantRole:
    ORDERING = "ORDERING"
    PERFORMING = "PERFORMING"
    AUTHORING = "AUTHORING"
    REFERRING = "REFERRING"
    ALL = (ORDERING, PERFORMING, AUTHORING, REFERRING)


# --------------------------------------------------------------------------
# Bulk ingestion
# --------------------------------------------------------------------------


class IngestStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"


class ItemStatus:
    PENDING = "PENDING"
    INGESTED = "INGESTED"
    DUPLICATE = "DUPLICATE"
    FAILED = "FAILED"


@dataclass
class IngestJob:
    """A durable record of one bulk ingestion.

    Durable because the alternative is restarting a 10,000-file batch from zero
    after an interruption. The job row carries the plan; the item rows carry
    what actually happened to each file, which is also the audit trail for why
    a given document is -- or is not -- in the case.
    """
    case_id: str
    source: str
    status: str = IngestStatus.PENDING
    total: int = 0
    worker_count: int = 1
    chunk_size: int = 200
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    note: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)


@dataclass
class IngestItem:
    """One file's fate within a job.

    `error` holds the reason a file failed. A failed item never blocks the
    batch: one unreadable file among ten thousand is a fact about that file,
    not grounds for discarding the other 9,999.
    """
    job_id: str
    path: str
    display_name: str
    ordinal: int
    status: str = ItemStatus.PENDING
    sha256: Optional[str] = None
    document_id: Optional[str] = None
    duplicate_of: Optional[str] = None
    error: Optional[str] = None
    parse_ms: Optional[int] = None
    id: str = field(default_factory=new_id)
