"""CARETRACE REST API.

Thin transport over caretrace.core (pipeline + engine) and caretrace.api.views
(read models). No audit logic lives here: routes fetch, serialise and return.
That separation is what makes the audit engine inspectable and testable on its
own, and it is a stated design requirement of the system.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (BackgroundTasks, Depends, FastAPI, File, HTTPException,
                     UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from ..core import models as M
from ..core import bulk as B
from ..core import pipeline as P
from ..core.store import Store
from ..demo import case_ct_demo_001 as DEMO
from ..demo.render_pdfs import PDF_DIR, render_all
from . import views as V

DISCLAIMER = (
    "CARETRACE is a research/prototype evidence-auditing system. It does not "
    "provide medical diagnosis or treatment recommendations and has not been "
    "clinically validated."
)

ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
UPLOAD_DIR = DATA_DIR / "uploads"

app = FastAPI(
    title="CARETRACE",
    description="Evidence audit for fragmented medical records. " + DISCLAIMER,
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        _store = Store(DATA_DIR / "caretrace.db")
    return _store


def _case_or_404(store: Store, case_id: str) -> dict:
    case = store.case(case_id)
    if not case:
        raise HTTPException(404, f"Case {case_id} not found")
    return case


# --------------------------------------------------------------------------
# Meta
# --------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "disclaimer": DISCLAIMER}


@app.get("/api/meta")
def meta() -> dict:
    """Vocabularies the UI renders — served from the engine, not duplicated."""
    from ..packs.medical import lexicon as LX
    return {
        "disclaimer": DISCLAIMER,
        "doc_types": [{"key": k, "label": M.DocType.LABELS.get(k, k)}
                      for k in M.DocType.ALL],
        "statuses": [M.Status.VERIFIED, M.Status.DOCUMENTED, M.Status.CHANGED,
                     M.Status.CONFLICT, M.Status.MISSING, M.Status.UNRESOLVED],
        "rel_types": M.RelType.ALL,
        "concepts": [{"key": k, "label": c.label, "unit": c.canonical_unit}
                     for k, c in sorted(LX.CONCEPTS.items())],
        "engine_version": P.ENGINE_VERSION,
    }


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------


@app.get("/api/cases")
def list_cases(store: Store = Depends(get_store)) -> list[dict]:
    return store.cases()


@app.post("/api/cases", status_code=201)
def create_case(payload: dict, store: Store = Depends(get_store)) -> dict:
    ref = (payload.get("case_ref") or "").strip() or f"CASE-{len(store.cases()) + 1:03d}"
    case = store.insert(M.Case(
        case_ref=ref,
        subject_label=(payload.get("subject_label") or "Unlabelled subject").strip(),
        subject_dob=payload.get("subject_dob"),
        is_synthetic=bool(payload.get("is_synthetic", False)),
        notes=payload.get("notes"),
    ))
    store.commit()
    return store.case(case.id)


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, store: Store = Depends(get_store)) -> dict:
    _case_or_404(store, case_id)
    return V.case_summary(store, case_id)


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: str, store: Store = Depends(get_store)):
    """Explicit deletion. Uploaded files are removed with the case record."""
    _case_or_404(store, case_id)
    for doc in store.documents(case_id):
        p = Path(doc["stored_path"])
        if p.is_file() and UPLOAD_DIR in p.parents:
            p.unlink(missing_ok=True)
    store.delete_case(case_id)
    store.commit()
    return JSONResponse(status_code=204, content=None)


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


@app.get("/api/cases/{case_id}/documents")
def list_documents(case_id: str, store: Store = Depends(get_store)) -> list[dict]:
    _case_or_404(store, case_id)
    return V.documents(store, case_id)


@app.post("/api/cases/{case_id}/documents", status_code=201)
async def upload_documents(case_id: str, files: list[UploadFile] = File(...),
                           store: Store = Depends(get_store)) -> dict:
    _case_or_404(store, case_id)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    existing_docs = store.documents(case_id)
    # Content hash -> display name, so a file already in the case is reported as
    # a duplicate instead of being ingested twice under a second row.
    seen: dict[str, str] = {d["sha256"]: d["filename"]
                            for d in existing_docs if d.get("sha256")}
    accepted, rejected, duplicates = [], [], []
    ordinal = len(existing_docs)

    for i, up in enumerate(files, start=1):
        name = Path(up.filename or f"document_{i}").name
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            rejected.append({"filename": name,
                             "reason": f"Unsupported file type '{suffix}'. "
                                       f"Accepted: PDF, PNG, JPG."})
            continue

        # Write to a per-request temporary name first. Two files submitted in
        # one batch under the SAME filename must not resolve to one path, or
        # the second silently overwrites the first while both database rows
        # survive -- the source viewer would then show the wrong document.
        staging = case_dir / f".incoming-{uuid.uuid4().hex}{suffix}"
        digest = hashlib.sha256()
        written, oversized = 0, False
        # The file must be fully written and CLOSED before ingestion reads it
        # back: the pipeline opens the path on disk, not the upload stream.
        with staging.open("wb") as fh:
            while chunk := await up.read(1 << 20):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    oversized = True
                    break
                digest.update(chunk)
                fh.write(chunk)
        if oversized:
            staging.unlink(missing_ok=True)
            rejected.append({"filename": name,
                             "reason": "File exceeds the 25 MB limit."})
            continue
        if written == 0:
            staging.unlink(missing_ok=True)
            rejected.append({"filename": name, "reason": "File is empty."})
            continue

        sha = digest.hexdigest()
        if sha in seen:
            staging.unlink(missing_ok=True)
            duplicates.append({"filename": name, "duplicate_of": seen[sha],
                               "sha256": sha,
                               "reason": "Identical content is already in this "
                                         "case; not ingested a second time."})
            continue

        # Content-addressed final name: unique per distinct file, and stable
        # for the same bytes. The operator's filename is display metadata.
        dest = case_dir / f"{sha[:16]}{suffix}"
        staging.replace(dest)
        seen[sha] = name
        ordinal += 1
        doc, _pages = P.ingest_document(store, case_id, dest, ordinal,
                                        display_name=name)
        accepted.append(doc.filename)

    store.commit()
    return {"accepted": accepted, "rejected": rejected,
            "duplicates": duplicates,
            "documents": V.documents(store, case_id)}


@app.get("/api/documents/{document_id}")
def get_document(document_id: str, store: Store = Depends(get_store)) -> dict:
    detail = V.document_detail(store, document_id)
    if not detail:
        raise HTTPException(404, "Document not found")
    return detail


@app.get("/api/documents/{document_id}/text")
def get_document_text(document_id: str, download: bool = False,
                      store: Store = Depends(get_store)):
    """The immutable raw text exactly as the parser saw it.

    Served from the raw_extractions row, not re-parsed on demand: what a
    reviewer downloads is byte-identical to what every fact was derived from.
    """
    row = store.q1("SELECT * FROM raw_extractions WHERE document_id = ?",
                   (document_id,))
    doc = store.q1("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not doc:
        raise HTTPException(404, "Document not found")
    if not row:
        raise HTTPException(404, "No raw extraction recorded for this document")
    if download:
        stem = Path(doc["filename"]).stem
        return PlainTextResponse(
            row["text"], headers={
                "Content-Disposition": f'attachment; filename="{stem}.txt"'})
    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "text": row["text"],
        "text_sha256": row["text_sha256"],
        "char_count": row["char_count"],
        "page_offsets": json.loads(row["page_offsets"]),
        "method": row["method"],
        "tool": {"name": row["tool_name"], "version": row["tool_version"]},
        "confidence": row["confidence"],
        "has_text_layer": bool(row["has_text_layer"]),
        "note": row["note"],
        "immutable": True,
    }


@app.get("/api/documents/{document_id}/file")
def get_document_file(document_id: str, store: Store = Depends(get_store)):
    doc = store.q1("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not doc:
        raise HTTPException(404, "Document not found")
    path = Path(doc["stored_path"])
    if not path.is_file():
        raise HTTPException(404, "Stored file is no longer available")
    return FileResponse(path, filename=doc["filename"])


# --------------------------------------------------------------------------
# Processing
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Bulk ingestion
# --------------------------------------------------------------------------


@app.post("/api/cases/{case_id}/ingest/bulk", status_code=202)
def start_bulk_ingest(case_id: str, background: BackgroundTasks,
                      source: str, workers: int = B.DEFAULT_WORKERS,
                      chunk_size: int = B.CHUNK, recursive: bool = True,
                      wait: bool = False,
                      store: Store = Depends(get_store)) -> dict:
    """Ingest a directory (or archive) of documents into a case.

    Returns 202 with a job id: a ten-thousand-file corpus takes longer than any
    reasonable request timeout, so the work runs in the background and progress
    is polled. `wait=true` runs it inline, which is what the tests use.

    The job plan is committed before this returns, so the job is resumable even
    if the process dies moments later.
    """
    _case_or_404(store, case_id)
    src = Path(source).expanduser()
    if not src.exists():
        raise HTTPException(status_code=400,
                            detail=f"Source not found: {source}")

    staged: Optional[Path] = None
    if src.is_file() and src.suffix.lower() in {".zip", ".tar", ".gz", ".tgz"}:
        # Archives are unpacked to a staging directory the ingester can walk.
        staged = Path(tempfile.mkdtemp(prefix="caretrace-bulk-"))
        try:
            shutil.unpack_archive(str(src), str(staged))
        except Exception as exc:                  # noqa: BLE001
            shutil.rmtree(staged, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"Could not unpack archive: {type(exc).__name__}") from exc
        src = staged

    job = B.plan_job(store, case_id, src, workers=max(1, workers),
                     chunk_size=max(1, chunk_size), recursive=recursive)
    if wait:
        result = B.run_job(store, job.id)
        return {"job": B.job_progress(store, job.id), "result": result}
    background.add_task(B.run_job, store, job.id)
    return {"job": B.job_progress(store, job.id),
            "note": "Ingestion running. Poll the job endpoint for progress."}


@app.get("/api/ingest/jobs/{job_id}")
def get_ingest_job(job_id: str, store: Store = Depends(get_store)) -> dict:
    """Job progress, safe to poll while the job runs."""
    try:
        prog = B.job_progress(store, job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such ingest job")
    # Failures are reported with the job, not hidden behind a second call: a
    # batch that silently dropped files is the failure mode to avoid.
    prog["failures"] = B.failed_items(store, job_id, limit=50)
    return prog


@app.get("/api/cases/{case_id}/ingest/jobs")
def list_ingest_jobs(case_id: str, store: Store = Depends(get_store)) -> dict:
    _case_or_404(store, case_id)
    return {"jobs": store.q(
        "SELECT id, source, status, total, worker_count, started_at, "
        "finished_at FROM ingest_jobs WHERE case_id = ? "
        "ORDER BY created_at DESC", (case_id,))}


@app.post("/api/cases/{case_id}/process")
def process(case_id: str, store: Store = Depends(get_store)) -> dict:
    _case_or_404(store, case_id)
    if not store.documents(case_id):
        raise HTTPException(400, "No documents to process in this case.")
    result = P.process_case(store, case_id)
    return {"run": store.latest_run(case_id),
            "stages": result.stages,
            "counts": result.counts}


@app.get("/api/cases/{case_id}/run")
def get_run(case_id: str, store: Store = Depends(get_store)) -> dict:
    _case_or_404(store, case_id)
    run = store.latest_run(case_id)
    if not run:
        raise HTTPException(404, "This case has not been processed yet.")
    return run


# --------------------------------------------------------------------------
# Evidence views
# --------------------------------------------------------------------------


def _view(fn):
    def route(case_id: str, store: Store = Depends(get_store)):
        _case_or_404(store, case_id)
        return fn(store, case_id)
    return route


app.get("/api/cases/{case_id}/patients")(_view(V.patients))
app.get("/api/cases/{case_id}/codings")(_view(V.codings))
app.get("/api/cases/{case_id}/facts")(_view(V.facts))
app.get("/api/cases/{case_id}/claims")(_view(V.claims))
app.get("/api/cases/{case_id}/medications")(_view(V.medications))
app.get("/api/cases/{case_id}/changes")(_view(V.changes))
app.get("/api/cases/{case_id}/series")(_view(V.series))
app.get("/api/cases/{case_id}/conflicts")(_view(V.conflicts))
app.get("/api/cases/{case_id}/evidence-gaps")(_view(V.evidence_gaps))
app.get("/api/cases/{case_id}/timeline")(_view(V.timeline))
app.get("/api/cases/{case_id}/graph")(_view(V.graph))
app.get("/api/cases/{case_id}/brief")(_view(V.brief))


@app.get("/api/sources/{source_id}")
def get_source(source_id: str, store: Store = Depends(get_store)) -> dict:
    """The provenance endpoint: a fact's exact document, page and text."""
    src = store.source(source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    page = store.q1(
        "SELECT * FROM document_pages WHERE document_id = ? AND page_number = ?",
        (src["document_id"], src["page_number"]))
    return {"source": src, "page_text": (page or {}).get("text", ""),
            "document": store.q1("SELECT * FROM documents WHERE id = ?",
                                 (src["document_id"],))}


# --------------------------------------------------------------------------
# Demo case
# --------------------------------------------------------------------------


@app.post("/api/demo", status_code=201)
def load_demo(reset: bool = True, store: Store = Depends(get_store)) -> dict:
    """Create (or reset) the synthetic demonstration case CT-DEMO-001.

    The PDFs are rendered from the corpus module and then ingested through the
    SAME path as an upload, so the demo exercises the real pipeline rather than
    a shortcut.
    """
    existing = next((c for c in store.cases()
                     if c["case_ref"] == DEMO.CASE["case_ref"]), None)
    if existing and not reset:
        return V.case_summary(store, existing["id"])
    if existing:
        store.delete_case(existing["id"])
        store.commit()

    render_all(PDF_DIR)
    case = store.insert(M.Case(**DEMO.CASE))
    store.commit()
    for i, path in enumerate(sorted(PDF_DIR.glob("*.pdf")), start=1):
        P.ingest_document(store, case.id, path, i)
    store.commit()
    return V.case_summary(store, case.id)


# --------------------------------------------------------------- terminology
@app.get("/api/terminology/providers")
def terminology_providers() -> dict:
    """Live provider status for the terminology admin screen.

    Probes each provider and reports why it is or is not usable. Never returns
    a credential value -- only which fields are present.
    """
    from ..terminology.resolver import TerminologyResolver
    res = TerminologyResolver()
    providers = res.health()
    return {
        "providers": providers,
        "active": [p["key"] for p in providers if p["state"] == "ACTIVE"],
        "note": ("A provider that is unlicensed or unreachable reduces "
                 "annotation coverage only. Conflict, change and gap detection "
                 "read the packs' own concepts and never a terminology "
                 "service, so audit results do not depend on this screen."),
    }


@app.get("/api/terminology/config")
def terminology_config() -> dict:
    """Which terminology settings are configured, and the variable names to set.

    Secret values are reported as "<set>" and never echoed.
    """
    from ..terminology.config import ENV, TerminologyConfig
    cfg = TerminologyConfig.from_env()
    return {"configured": cfg.redacted(),
            "env_vars": {k: dict(v) for k, v in ENV.items()},
            "timeout": cfg.timeout}


# --------------------------------------------------------------------------
# Static frontend
# --------------------------------------------------------------------------

if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


def main() -> None:
    import uvicorn
    uvicorn.run("caretrace.api.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
