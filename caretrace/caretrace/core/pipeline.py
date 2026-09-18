"""The CARETRACE processing pipeline.

    INGEST -> CLASSIFY -> EXTRACT -> NORMALIZE -> FACTS -> CLAIMS -> EVENTS
    -> RESOLVE ENTITIES -> RELATIONSHIPS -> CHANGES -> CONFLICTS -> GAPS -> AUDIT

Each stage is a named function recorded on the ProcessingRun, so the pipeline
that the architecture describes is the pipeline that actually executes and the
UI can show real per-stage counts.

Ingestion (document -> page text) is the only stage that touches file formats.
Everything after it operates on text and is deterministic.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Callable, Optional

from ..packs.medical import lexicon as LX
from . import models as M
from . import registry
from .engine import changes as changes_engine
from .engine import claims_engine
from .engine import conflicts as conflicts_engine
from .engine import gaps as gaps_engine
from .extract import Extractor, RuleExtractor
from .store import Store

ENGINE_VERSION = "caretrace-engine/1.0"

#: The pipeline's stages, in execution order. Declared rather than inferred so
#: a run can be checked against what the pipeline says it does. Note where
#: RESOLVE_TERMINOLOGY sits: after GENERATE_AUDIT, because vocabulary
#: annotation is advisory and no audit result may depend on it.
STAGES: tuple[str, ...] = (
    "INGEST", "CLASSIFY", "EXTRACT", "NORMALIZE",
    "CREATE_FACTS", "CREATE_CLAIMS", "CREATE_EVENTS", "BUILD_REGISTRY",
    "RESOLVE_ENTITIES",
    "DETECT_CHANGES", "DETECT_CONFLICTS", "RESOLVE_CLAIMS",
    "BUILD_RELATIONSHIPS", "DETECT_GAPS", "GENERATE_AUDIT",
    "RESOLVE_TERMINOLOGY",
)


# --------------------------------------------------------------------------
# Ingestion: the only format-aware seam.
# --------------------------------------------------------------------------

def read_pdf_pages(path: Path) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def read_text_pages(path: Path) -> list[str]:
    return [path.read_text(encoding="utf-8", errors="replace")]


def read_image_pages(path: Path) -> list[str]:
    """Images require OCR, which is a modular extension point.

    The MVP ships no OCR engine. Rather than invent text, the document is
    ingested with an empty page and reported as extraction-incomplete.
    """
    return [""]


READERS: dict[str, Callable[[Path], list[str]]] = {
    ".pdf": read_pdf_pages,
    ".txt": read_text_pages,
    ".png": read_image_pages,
    ".jpg": read_image_pages,
    ".jpeg": read_image_pages,
}

# How each format's text was obtained, recorded on the raw extraction so a
# reviewer can tell a clean text layer from an OCR guess. Never inferred later.
METHODS: dict[str, str] = {
    ".pdf": M.ExtractionMethod.PDF_TEXT_LAYER,
    ".txt": M.ExtractionMethod.PLAIN_TEXT,
    ".png": M.ExtractionMethod.OCR,
    ".jpg": M.ExtractionMethod.OCR,
    ".jpeg": M.ExtractionMethod.OCR,
}


def _tool_for(suffix: str) -> tuple[Optional[str], Optional[str]]:
    if suffix == ".pdf":
        try:
            import pypdf
            return "pypdf", getattr(pypdf, "__version__", "unknown")
        except Exception:                                # pragma: no cover
            return "pypdf", "unavailable"
    if suffix == ".txt":
        return "builtin-text", "1.0"
    return None, None


def write_raw_extraction(store: Store, doc: M.Document,
                         pages_text: list[str],
                         suffix: str,
                         sidecar_dir: Optional[Path] = None,
                         ) -> M.RawExtraction:
    """Persist the complete parser output verbatim, once, per document.

    The concatenated text plus per-page offsets is the immutable anchor for
    every later provenance claim. A .txt sidecar is written beside the original
    binary so the operator can retain and re-read the source outside CARETRACE,
    which the requirement to "keep all original report data as txt" asks for.
    """
    sep = "\n\f\n"          # form feed: an explicit, greppable page boundary
    offsets, cursor, parts = [], 0, []
    for txt in pages_text:
        parts.append(txt)
        offsets.append([cursor, cursor + len(txt)])
        cursor += len(txt) + len(sep)
    full = sep.join(parts)

    method = METHODS.get(suffix, M.ExtractionMethod.NONE)
    tool, version = _tool_for(suffix)
    has_layer = 1 if full.strip() else 0
    note = None
    if not has_layer:
        note = ("No text layer was recovered from this document. No text is "
                "invented; the document is reported as extraction-incomplete.")

    sidecar = None
    if sidecar_dir is not None:
        try:
            sidecar_dir.mkdir(parents=True, exist_ok=True)
            p = sidecar_dir / f"{Path(doc.stored_path or doc.filename).stem}.txt"
            p.write_text(full, encoding="utf-8")
            sidecar = str(p)
        except OSError:
            sidecar = None      # sidecar is a convenience; the row is the record

    return store.insert(M.RawExtraction(
        document_id=doc.id,
        text=full,
        text_sha256=hashlib.sha256(full.encode("utf-8")).hexdigest(),
        char_count=len(full),
        page_offsets=json.dumps(offsets),
        method=method,
        tool_name=tool,
        tool_version=version,
        confidence=None if method == M.ExtractionMethod.OCR else 1.0,
        has_text_layer=has_layer,
        note=note,
        sidecar_path=sidecar,
    ))


def ingest_document(store: Store, case_id: str, path: Path, ordinal: int,
                    display_name: Optional[str] = None,
                    ) -> tuple[M.Document, list[M.DocumentPage]]:
    """Ingest one file already at rest on disk.

    `path` is where the bytes live, which for uploads is a content-addressed
    name; `display_name` is what the operator called the file. Keeping the two
    apart is what stops two same-named uploads from sharing one path and
    silently overwriting each other's provenance.
    """
    data = path.read_bytes()
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        pages_text: list[str] = []
        note = f"Unsupported file type '{path.suffix}'. No text was extracted."
        status = M.Status.MISSING
    else:
        pages_text = reader(path)
        note = None
        status = "INGESTED"

    doc = store.insert(M.Document(
        case_id=case_id,
        filename=display_name or path.name,
        doc_type=M.DocType.OTHER,
        doc_date=None,
        page_count=len(pages_text),
        byte_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        stored_path=str(path),
        upload_status="UPLOADED",
        processing_status=status,
        processing_note=note,
        ordinal=ordinal,
    ))
    pages = [store.insert(M.DocumentPage(document_id=doc.id, page_number=i,
                                         text=txt))
             for i, txt in enumerate(pages_text, start=1)]
    # Written once, immediately after parsing and before any interpretation.
    write_raw_extraction(store, doc, pages_text, path.suffix.lower(),
                         sidecar_dir=path.parent / "raw_text")
    return doc, pages


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------

class PipelineResult:
    """Outcome of one audit run.

    `stages` is the per-stage log (name, row count, duration) that the
    processing view replays, so the pipeline the user watches is the pipeline
    that actually ran rather than an animation.
    """

    def __init__(self, run: M.ProcessingRun, counts: dict,
                 stages: Optional[list[dict]] = None):
        self.run = run
        self.counts = counts
        self.stages = stages or []


def _display(prefix: str, n: int) -> str:
    return f"{prefix}-{n:03d}"


def process_case(store: Store, case_id: str,
                 extractor: Optional[Extractor] = None,
                 resolver: Optional["TerminologyResolver"] = None,
                 resolve_terminology: bool = True) -> PipelineResult:
    """Run the full audit for a case whose documents are already ingested.

    Derived rows (facts, claims, ..., gaps) are rebuilt from scratch on every
    run; documents and pages are never touched.

    Terminology resolution runs LAST and is strictly additive: it reads the
    facts, medications and claims the audit already produced and writes only to
    `codings`. Every count returned in `PipelineResult` is computed before it
    runs, so a terminology outage -- or a missing licence -- cannot change a
    conflict, a change or a gap.
    """
    extractor = extractor or RuleExtractor()

    # The reset must happen BEFORE the run row is created: clear_derived also
    # drops processing_runs for this case, so inserting first would delete the
    # very run being recorded.
    store.clear_derived(case_id)

    run = store.insert(M.ProcessingRun(case_id=case_id,
                                       engine_version=ENGINE_VERSION))
    store.commit()
    stages: list[dict] = []

    def stage(name: str, **counts):
        assert name in STAGES, f"undeclared pipeline stage {name!r}"
        stages.append({"stage": name, **counts})

    documents = [M.Document(**r) for r in store.rows("documents", case_id,
                                                     order="ordinal")]
    stage("INGEST", documents=len(documents),
          pages=sum(d.page_count for d in documents))

    # ---------------- CLASSIFY ----------------
    pages_by_doc: dict[str, list[M.DocumentPage]] = {}
    for doc in documents:
        prows = store.pages(doc.id)
        pages_by_doc[doc.id] = [M.DocumentPage(**r) for r in prows]
        full_text = "\n".join(p.text for p in pages_by_doc[doc.id])
        doc_type = extractor.classify(full_text, doc.filename)
        doc_date, _prec = extractor.document_date(full_text)
        store.update("documents", doc.id, doc_type=doc_type, doc_date=doc_date)
        doc.doc_type, doc.doc_date = doc_type, doc_date
    stage("CLASSIFY", documents=len(documents),
          types=len({d.doc_type for d in documents}))

    # ---------------- EXTRACT + NORMALIZE ----------------
    raw_by_doc: dict[str, list[tuple[M.DocumentPage, object]]] = {}
    n_items = 0
    for doc in documents:
        collected: list[tuple[M.DocumentPage, object]] = []
        for page in pages_by_doc[doc.id]:
            if not page.text.strip():
                continue
            for item in extractor.extract_page(page.text, doc.doc_type, doc.doc_date):
                collected.append((page, item))
        raw_by_doc[doc.id] = collected
        n_items += len(collected)
        if not collected:
            store.update(
                "documents", doc.id,
                processing_status="EXTRACTION_INCOMPLETE",
                processing_note=("Unable to identify structured observations, "
                                 "claims or medications in this document. "
                                 "Requires review."))
        else:
            store.update("documents", doc.id, processing_status="PROCESSED",
                         processing_note=None)
    stage("EXTRACT", items=n_items)
    stage("NORMALIZE", concepts=len({
        it.payload.get("concept") for items in raw_by_doc.values()
        for _p, it in items if it.kind == "OBSERVATION"}))

    # ---------------- SOURCES + FACTS / CLAIMS / MEDICATIONS / EVENTS ----------------
    facts: list[M.Fact] = []
    claims: list[M.Claim] = []
    medications: list[M.Medication] = []
    events: list[M.Event] = []
    references: list[M.DocumentReference] = []
    doc_of_source: dict[str, str] = {}

    counters = {"F": 0, "C": 0, "M": 0, "E": 0, "R": 0}

    for doc in documents:
        for page, item in raw_by_doc[doc.id]:
            src = store.insert(M.Source(
                case_id=case_id, document_id=doc.id, page_id=page.id,
                page_number=page.page_number, source_text=item.source_text,
                char_start=item.char_start, char_end=item.char_end))
            doc_of_source[src.id] = doc.id
            pl = item.payload

            if item.kind == "OBSERVATION":
                counters["F"] += 1
                facts.append(store.insert(M.Fact(
                    case_id=case_id, display_id=_display("F", counters["F"]),
                    concept=pl["concept"], surface_form=pl["surface_form"],
                    source_id=src.id, evidence_type=M.EvidenceType.OBSERVATION,
                    value_num=pl["value"], value_text=None, unit=pl["unit"],
                    obs_date=pl["date"], date_precision=pl["date_precision"],
                    confidence=item.confidence)))
            elif item.kind == "FINDING":
                # A qualitative finding is a fact with a text value. Same fact
                # table, same provenance, same conflict machinery -- the only
                # difference is that the value is a documented phrase rather
                # than a number.
                counters["F"] += 1
                facts.append(store.insert(M.Fact(
                    case_id=case_id, display_id=_display("F", counters["F"]),
                    concept=pl["concept"], surface_form=pl["surface_form"],
                    source_id=src.id, evidence_type=M.EvidenceType.OBSERVATION,
                    value_num=None, value_text=pl["value_text"],
                    value_key=pl["value_key"], unit=None,
                    obs_date=pl["date"], date_precision=pl["date_precision"],
                    confidence=item.confidence)))
            elif item.kind == "CLAIM":
                counters["C"] += 1
                claims.append(store.insert(M.Claim(
                    case_id=case_id, display_id=_display("C", counters["C"]),
                    claim_text=pl["claim_text"], source_id=src.id,
                    claim_type=pl["claim_type"], claim_date=pl["date"],
                    date_precision=pl["date_precision"],
                    confidence=item.confidence,
                    evidence_status=M.ClaimEvidenceStatus.NOT_ASSESSED)))
            elif item.kind == "MEDICATION":
                counters["M"] += 1
                medications.append(store.insert(M.Medication(
                    case_id=case_id, display_id=_display("M", counters["M"]),
                    drug_name=pl["drug_name"], drug_norm=pl["drug_norm"],
                    source_id=src.id, dose=pl["dose"], unit=pl["unit"],
                    frequency=pl["frequency"], route=pl["route"],
                    status=pl["status"], start_date=pl["start_date"],
                    stop_date=pl.get("stop_date"), record_date=pl["record_date"],
                    confidence=item.confidence)))
            elif item.kind == "EVENT":
                counters["E"] += 1
                events.append(store.insert(M.Event(
                    case_id=case_id, display_id=_display("E", counters["E"]),
                    event_type=pl["event_type"], label=pl["label"],
                    source_id=src.id, event_date=pl["date"],
                    detail=pl.get("detail"))))
            elif item.kind == "REFERENCE":
                counters["R"] += 1
                references.append(store.insert(M.DocumentReference(
                    case_id=case_id, display_id=_display("R", counters["R"]),
                    label=pl["label"], source_id=src.id,
                    doc_type_hint=pl["doc_type_hint"],
                    resolved_document_id=None, status=M.Status.MISSING)))
    store.commit()
    stage("CREATE_FACTS", facts=len(facts))
    stage("CREATE_CLAIMS", claims=len(claims))
    stage("CREATE_EVENTS", events=len(events), references=len(references))

    # ---------------- RESOLVE ENTITIES ----------------
    def doc_of_fact(f: M.Fact) -> Optional[str]:
        return doc_of_source.get(f.source_id)

    def doc_of_med(m: M.Medication) -> Optional[str]:
        return doc_of_source.get(m.source_id)

    doc_by_id = {d.id: d for d in documents}

    def doc_type_of_med(m: M.Medication) -> Optional[str]:
        did = doc_of_med(m)
        return doc_by_id[did].doc_type if did in doc_by_id else None

    def doc_label(doc_id: str) -> str:
        d = doc_by_id.get(doc_id)
        return d.filename if d else doc_id

    # ---------------- BUILD REGISTRY ----------------
    # Identity resolution runs on documents, so it needs nothing from the
    # evidence rows -- but it must run before detection, because detection is
    # partitioned by patient and cannot be if nobody knows who is who.
    case_row = store.case(case_id) or {}
    reg_counts = registry.build_registry(
        store, case_id, documents, pages_by_doc,
        is_synthetic=bool(case_row.get("is_synthetic", 1)))
    stage("BUILD_REGISTRY", **reg_counts)

    # Which patient each document was linked to. A document under review has no
    # patient and is deliberately absent from this map.
    patient_of_doc: dict[str, str] = {
        r["document_id"]: r["patient_id"] for r in store.q(
            "SELECT document_id, patient_id FROM identity_links "
            "WHERE case_id = ? AND patient_id IS NOT NULL", (case_id,))}

    def patient_of_fact(f: M.Fact) -> Optional[str]:
        did = doc_of_source.get(f.source_id)
        return patient_of_doc.get(did) if did else None

    def patient_of_med(m: M.Medication) -> Optional[str]:
        did = doc_of_source.get(m.source_id)
        return patient_of_doc.get(did) if did else None

    def partition(items, key_of):
        """Group evidence rows by patient.

        Rows whose document is unresolved are grouped under None and compared
        only with each other. That is the conservative choice in both
        directions: comparing an unresolved document against a patient's record
        could fabricate a conflict between two different people, and silently
        dropping it would hide evidence the corpus actually contains.
        """
        out: dict[Optional[str], list] = {}
        for it in items:
            out.setdefault(key_of(it), []).append(it)
        return out

    facts_by_patient = partition(facts, patient_of_fact)
    meds_by_patient = partition(medications, patient_of_med)

    stage("RESOLVE_ENTITIES",
          concepts=len({f.concept for f in facts}),
          drugs=len({m.drug_norm for m in medications}),
          patients=len([k for k in facts_by_patient if k]))

    # ---------------- CHANGES ----------------
    # Every detector below runs once PER PATIENT. Two haemoglobin values
    # belonging to two different people are not a change and not a conflict,
    # and a detector handed the union of both records would report them as one.
    change_rows: list[M.Change] = []
    change_rels: list[M.Relationship] = []
    dup_rels: list[M.Relationship] = []
    for group in facts_by_patient.values():
        rows, rels = changes_engine.detect_changes(group)
        change_rows += rows
        change_rels += rels
        dup_rels += changes_engine.detect_duplicates(group)
    for i, ch in enumerate(change_rows, start=1):
        store.insert(replace(ch, display_id=_display("CH", i)))
    stage("DETECT_CHANGES", changes=len(change_rows), duplicates=len(dup_rels))

    # ---------------- CONFLICTS ----------------
    num_conflicts: list[M.Conflict] = []
    num_rels: list[M.Relationship] = []
    status_conflicts: list[M.Conflict] = []
    status_rels: list[M.Relationship] = []
    for group in facts_by_patient.values():
        c, r = conflicts_engine.detect_numeric_conflicts(group, doc_of_fact)
        num_conflicts += c
        num_rels += r
        c, r = conflicts_engine.detect_status_conflicts(group, doc_of_fact)
        status_conflicts += c
        status_rels += r

    med_conflicts: list[M.Conflict] = []
    med_rels: list[M.Relationship] = []
    implicated: list[M.Medication] = []
    for group in meds_by_patient.values():
        c, r, imp = conflicts_engine.detect_medication_conflicts(
            group, doc_of_med, doc_type_of_med, doc_label)
        med_conflicts += c
        med_rels += r
        implicated += imp
    all_conflicts = num_conflicts + status_conflicts + med_conflicts
    for i, cf in enumerate(all_conflicts, start=1):
        store.insert(replace(cf, display_id=_display("CF", i)))
    stage("DETECT_CONFLICTS", numeric=len(num_conflicts),
          status=len(status_conflicts), medication=len(med_conflicts))

    # ---------------- CLAIM EVIDENCE ----------------
    # A claim is assessed against its own patient's evidence only. Supporting a
    # claim with another person's laboratory result is the same class of error
    # as a wrong merge, arrived at from the other direction.
    def patient_of_claim(c: M.Claim) -> Optional[str]:
        did = doc_of_source.get(c.source_id)
        return patient_of_doc.get(did) if did else None

    claim_results: list[dict] = []
    claim_rels: list[M.Relationship] = []
    for pid, group in partition(claims, patient_of_claim).items():
        res, rels = claims_engine.resolve_claims(
            group, facts_by_patient.get(pid, []))
        claim_results += res
        claim_rels += rels
    for res in claim_results:
        store.update("claims", res["claim"].id, evidence_status=res["status"])
    stage("RESOLVE_CLAIMS", assessed=len(claim_results))

    # ---------------- RELATIONSHIPS ----------------
    for rel in (change_rels + dup_rels + num_rels + status_rels
                + med_rels + claim_rels):
        store.insert(rel)
    n_rels = (len(change_rels) + len(dup_rels) + len(num_rels)
              + len(status_rels) + len(med_rels) + len(claim_rels))
    stage("BUILD_RELATIONSHIPS", relationships=n_rels)

    # ---------------- EVIDENCE GAPS ----------------
    def _citing_doc_id(ref):
        src = store.source(ref.source_id)
        return src["document_id"] if src else None

    def _citing_date(ref):
        doc = doc_by_id.get(_citing_doc_id(ref))
        return doc.doc_date if doc else None

    def _doc_terms(doc):
        """The document's own title, for matching a citation's study.

        A report names itself in its heading, so only the first few non-empty
        lines of page one are offered. Scanning the body instead would let a
        passing mention of another modality answer a citation -- and scanning
        the page header is worse still, since case references and MRNs contain
        letter runs ("CT-DEMO-001") that collide with study abbreviations.
        """
        pages = store.pages(doc.id)
        if not pages:
            return ""
        lines = [ln.strip() for ln in (pages[0]["text"] or "").splitlines()
                 if ln.strip()]
        return " ".join(lines[:3])

    ref_gaps, ref_resolved = gaps_engine.gaps_from_references(
        references, documents, _citing_date, _citing_doc_id, _doc_terms)
    # A satisfied citation is recorded as resolved: provenance should show
    # which uploaded document answered it, not merely that no gap was raised.
    for ref_id, doc_id in ref_resolved:
        store.update("document_references", ref_id,
                     resolved_document_id=doc_id, status="RESOLVED")
    gap_rows = (gaps_engine.gaps_from_claims(claim_results)
                + ref_gaps
                + gaps_engine.gaps_from_medications(implicated)
                + gaps_engine.gaps_from_followups(events, documents))
    for i, g in enumerate(gap_rows, start=1):
        store.insert(replace(g, display_id=_display("G", i)))
    stage("DETECT_GAPS", gaps=len(gap_rows))

    # ---------------- AUDIT ----------------
    traceable = sum(1 for f in facts if f.source_id) + \
                sum(1 for c in claims if c.source_id) + \
                sum(1 for m in medications if m.source_id)
    total_items = len(facts) + len(claims) + len(medications)
    counts = {
        "documents": len(documents),
        "pages": sum(d.page_count for d in documents),
        "facts": len(facts),
        "claims": len(claims),
        "medications": len(medications),
        "events": len(events),
        "changes": len(change_rows),
        "conflicts": len(all_conflicts),
        "evidence_gaps": len(gap_rows),
        "relationships": n_rels,
        "duplicates": len(dup_rels),
        "unresolved": sum(1 for c in all_conflicts if c.status == M.Status.UNRESOLVED),
        "source_traceability": (traceable / total_items) if total_items else 0.0,
    }
    stage("GENERATE_AUDIT", **{k: v for k, v in counts.items()
                               if k in ("changes", "conflicts", "evidence_gaps")})

    # ---------------- RESOLVE_TERMINOLOGY (advisory, additive) ----------------
    # Deliberately after GENERATE_AUDIT: `counts` is already fixed above, so
    # nothing this stage does can alter an audit result. It annotates the
    # record with vocabulary codes where a provider is licensed and reachable.
    if resolve_terminology:
        from ..terminology.resolver import TerminologyResolver
        res = resolver or TerminologyResolver()
        try:
            tr = res.resolve_case(store, case_id)
            stage("RESOLVE_TERMINOLOGY", **tr.as_dict())
            counts["codings"] = tr.coded
            counts["codings_assertable"] = tr.assertable
        except Exception as e:  # noqa: BLE001 - annotation must never fail a run
            # An annotation failure is reported, not raised: the audit above is
            # complete and correct without it.
            stage("RESOLVE_TERMINOLOGY", error=f"{type(e).__name__}: {e}",
                  coded=0)
            counts["codings"] = 0
            counts["codings_assertable"] = 0

    store.finish_run(run.id, stages=stages, status="COMPLETE")
    store.commit()
    run.stages, run.status = stages, "COMPLETE"
    return PipelineResult(run, counts, stages)
