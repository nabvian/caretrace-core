"""Bulk ingestion: many documents into one case, durably and resumably.

Three properties matter more than raw speed here, and the design trades speed
for each of them deliberately.

**Per-file isolation.** A corpus of ten thousand real reports contains
truncated PDFs, mislabelled extensions, and files that crash a parser. One of
them must not fail the batch. Every file is parsed inside its own try, and a
failure becomes a FAILED item with the exception text recorded -- a fact about
that file, not grounds for discarding the other 9,999.

**Durability.** Item status is written in the same transaction as the document
rows it produced. An item still PENDING after a crash therefore never
committed anything, so resuming a job means re-running exactly the PENDING
items. There is no separate reconciliation step and no window in which a
document exists but its item says otherwise.

**Serialized writes, parallel parsing.** Parsing runs in a thread pool; writing
does not, because SQLite gives one connection one writer and both ordinal
assignment and content dedupe need a single consistent view. So workers parse
and the caller writes, in chunked transactions.

What the pool buys was measured, and the answer is: nothing, for either
format currently supported. On small text reports the serialized writer
dominates so completely that worker count is irrelevant (~8,000 docs/s on one
worker, slower past two as coordination accrues). On PDFs -- the case the pool
was added for -- the measured speedup is 0.96x, because pypdf's text extraction
is pure Python and holds the GIL for its duration. Threads cannot parallelise
it. A process pool would, but could not be measured in the environment this was
built in, so no claim is made about it.

The pool is kept, at a default of one worker, for two honest reasons: it costs
nothing at one worker, and it is the seam where a parser that DOES release the
GIL (a C-extension text layer) or blocks on I/O (a network OCR service, which
is the planned extension) would parallelise for free. What is not claimed is a
speedup that this ingester does not currently deliver. bench_bulk.py reports
the sweep so the claim stays checkable.
"""
from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import models as M
from .pipeline import METHODS, READERS, write_raw_extraction
from .store import Store

# Extensions the ingester will attempt. Anything else is recorded as a failed
# item with a stated reason rather than skipped silently -- a file the operator
# handed us and we ignored is a documentation gap of our own making.
IMPORTABLE = set(READERS)

CHUNK = 200

# One, because the worker sweep in bench_bulk.py shows no format currently
# supported parses faster with more (see the module docstring). Raise it when a
# GIL-releasing or I/O-bound parser is plugged in -- not before.
DEFAULT_WORKERS = 1


class Parsed:
    """Parser output for one file, held in memory only until it is written."""

    __slots__ = ("item_id", "path", "display_name", "ordinal", "pages",
                 "sha256", "byte_size", "error", "parse_ms")

    def __init__(self, item_id: str, path: Path, display_name: str,
                 ordinal: int):
        self.item_id = item_id
        self.path = path
        self.display_name = display_name
        self.ordinal = ordinal
        self.pages: list[str] = []
        self.sha256: Optional[str] = None
        self.byte_size = 0
        self.error: Optional[str] = None
        self.parse_ms = 0


def _parse_one(p: Parsed) -> Parsed:
    """Read and parse a single file. Never raises: the error becomes data.

    Catching bare Exception is deliberate. A parser fed 10,000 real-world files
    can raise anything at all, and the caller's contract is that one bad file
    is isolated. An uncaught exception here would take the whole batch down,
    which is the exact failure this module exists to prevent.
    """
    t0 = time.perf_counter()
    try:
        data = p.path.read_bytes()
        p.byte_size = len(data)
        p.sha256 = hashlib.sha256(data).hexdigest()
        suffix = p.path.suffix.lower()
        reader = READERS.get(suffix)
        if reader is None:
            p.error = (f"Unsupported file type '{suffix}'. No text was "
                       f"extracted and no content was invented.")
        else:
            p.pages = reader(p.path)
    except Exception as exc:                      # noqa: BLE001 - see docstring
        p.error = f"{type(exc).__name__}: {exc}"
    p.parse_ms = int((time.perf_counter() - t0) * 1000)
    return p


# Files that are an artefact of the filesystem rather than something the
# operator handed us. These are the ONLY names excluded from a job, because a
# file that is skipped silently is a documentation gap of our own making.
_FS_NOISE = {".ds_store", "thumbs.db", "desktop.ini"}


def discover(source: Path, recursive: bool = True) -> list[Path]:
    """List every candidate file under a directory, or the file itself.

    Deliberately NOT filtered to supported extensions. A file the operator
    placed in the corpus and we quietly ignored is invisible to them; recorded
    as a failed item with a stated reason, it is reviewable. Only filesystem
    noise and dotfiles are excluded.

    Sorted so that ordinals are stable across runs: a resumed job must assign
    the same ordinal to the same file, or provenance ordering changes silently
    between attempts.
    """
    if source.is_file():
        return [source]
    it = source.rglob("*") if recursive else source.glob("*")
    return sorted(p for p in it
                  if p.is_file() and not p.name.startswith(".")
                  and p.name.lower() not in _FS_NOISE)


def plan_job(store: Store, case_id: str, source: Path,
             workers: int = DEFAULT_WORKERS, chunk_size: int = CHUNK,
             recursive: bool = True) -> M.IngestJob:
    """Record the job and one PENDING item per file, then commit.

    The plan is committed BEFORE any work starts. That is what makes the job
    resumable: after an interruption the item rows say exactly which files were
    intended, which is information that cannot be recovered from a directory
    listing that may itself have changed.
    """
    paths = discover(source, recursive=recursive)
    job = store.insert(M.IngestJob(
        case_id=case_id, source=str(source), total=len(paths),
        worker_count=workers, chunk_size=chunk_size))
    start_ordinal = len(store.documents(case_id))
    for i, path in enumerate(paths, start=1):
        store.insert(M.IngestItem(
            job_id=job.id, path=str(path), display_name=path.name,
            ordinal=start_ordinal + i))
    store.commit()
    return job


def run_job(store: Store, job_id: str,
            progress: Optional[Callable[[dict], None]] = None) -> dict:
    """Execute (or resume) a job. Returns measured counts.

    Only PENDING items are processed, which is what makes a second call a
    resume rather than a duplicate ingestion.
    """
    job = store.q1("SELECT * FROM ingest_jobs WHERE id = ?", (job_id,))
    if job is None:
        raise KeyError(f"no such ingest job: {job_id}")
    case_id = job["case_id"]
    store.conn.execute(
        "UPDATE ingest_jobs SET status = ?, started_at = COALESCE(started_at, ?) "
        "WHERE id = ?", (M.IngestStatus.RUNNING, M.now_iso(), job_id))
    store.commit()

    pending = store.q(
        "SELECT * FROM ingest_items WHERE job_id = ? AND status = ? "
        "ORDER BY ordinal", (job_id, M.ItemStatus.PENDING))

    # Content hashes already in the case, so a re-run or an overlapping corpus
    # reports a duplicate instead of ingesting the same bytes twice.
    seen: dict[str, str] = {
        d["sha256"]: d["filename"]
        for d in store.documents(case_id) if d.get("sha256")}

    counts = {"ingested": 0, "duplicate": 0, "failed": 0,
              "pages": 0, "bytes": 0}
    t0 = time.perf_counter()
    chunk_size = int(job["chunk_size"] or CHUNK)
    workers = max(1, int(job["worker_count"] or 1))

    def batches(rows: list, n: int) -> Iterable[list]:
        for i in range(0, len(rows), n):
            yield rows[i:i + n]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for batch in batches(pending, chunk_size):
            todo = [Parsed(r["id"], Path(r["path"]), r["display_name"],
                           r["ordinal"]) for r in batch]
            # Parse in parallel, write serially: see the module docstring.
            for p in pool.map(_parse_one, todo):
                _write_one(store, case_id, p, seen, counts)
            # One transaction per chunk. Committing per file would make fsync
            # the bottleneck; committing once at the end would put the whole
            # batch at risk and make resumption meaningless.
            store.commit()
            if progress:
                progress(dict(counts, elapsed_s=time.perf_counter() - t0))

    elapsed = time.perf_counter() - t0
    still_pending = store.q1(
        "SELECT COUNT(*) AS n FROM ingest_items WHERE job_id = ? AND status = ?",
        (job_id, M.ItemStatus.PENDING))["n"]
    status = (M.IngestStatus.COMPLETED if still_pending == 0
              else M.IngestStatus.INTERRUPTED)
    store.conn.execute(
        "UPDATE ingest_jobs SET status = ?, finished_at = ? WHERE id = ?",
        (status, M.now_iso(), job_id))
    store.commit()

    counts["elapsed_s"] = round(elapsed, 3)
    counts["docs_per_s"] = round(
        (counts["ingested"] + counts["duplicate"] + counts["failed"])
        / elapsed, 1) if elapsed > 0 else 0.0
    counts["status"] = status
    return counts


def _write_one(store: Store, case_id: str, p: Parsed,
               seen: dict[str, str], counts: dict) -> None:
    """Write one parsed file's rows and its item status together.

    Item status and document rows land in the same chunk transaction, so a
    crash can never leave a document whose item claims it was never ingested.
    """
    if p.error is not None:
        store.conn.execute(
            "UPDATE ingest_items SET status = ?, error = ?, sha256 = ?, "
            "parse_ms = ? WHERE id = ?",
            (M.ItemStatus.FAILED, p.error, p.sha256, p.parse_ms, p.item_id))
        counts["failed"] += 1
        return

    if p.sha256 in seen:
        store.conn.execute(
            "UPDATE ingest_items SET status = ?, sha256 = ?, duplicate_of = ?, "
            "parse_ms = ? WHERE id = ?",
            (M.ItemStatus.DUPLICATE, p.sha256, seen[p.sha256], p.parse_ms,
             p.item_id))
        counts["duplicate"] += 1
        return

    # An empty parse is ingested, not discarded: a page with no text layer is
    # evidence that a document exists and could not be read, which a reviewer
    # needs to see. Inventing text, or dropping the file, would both hide it.
    status = ("INGESTED" if any(t.strip() for t in p.pages)
              else M.Status.MISSING)
    note = None if status == "INGESTED" else (
        "No text layer found. The document is retained; no text was invented.")

    doc = store.insert(M.Document(
        case_id=case_id, filename=p.display_name, doc_type=M.DocType.OTHER,
        doc_date=None, page_count=len(p.pages), byte_size=p.byte_size,
        sha256=p.sha256, stored_path=str(p.path), upload_status="UPLOADED",
        processing_status=status, processing_note=note, ordinal=p.ordinal))
    for i, txt in enumerate(p.pages, start=1):
        store.insert(M.DocumentPage(document_id=doc.id, page_number=i,
                                    text=txt))
    write_raw_extraction(store, doc, p.pages, p.path.suffix.lower())

    seen[p.sha256] = p.display_name
    store.conn.execute(
        "UPDATE ingest_items SET status = ?, sha256 = ?, document_id = ?, "
        "parse_ms = ? WHERE id = ?",
        (M.ItemStatus.INGESTED, p.sha256, doc.id, p.parse_ms, p.item_id))
    counts["ingested"] += 1
    counts["pages"] += len(p.pages)
    counts["bytes"] += p.byte_size


def job_progress(store: Store, job_id: str) -> dict:
    """Current state of a job, safe to poll while it runs."""
    job = store.q1("SELECT * FROM ingest_jobs WHERE id = ?", (job_id,))
    if job is None:
        raise KeyError(job_id)
    by_status = {r["status"]: r["n"] for r in store.q(
        "SELECT status, COUNT(*) AS n FROM ingest_items WHERE job_id = ? "
        "GROUP BY status", (job_id,))}
    done = sum(v for k, v in by_status.items() if k != M.ItemStatus.PENDING)
    return {
        "job_id": job_id, "case_id": job["case_id"], "status": job["status"],
        "source": job["source"], "total": job["total"], "processed": done,
        "pending": by_status.get(M.ItemStatus.PENDING, 0),
        "ingested": by_status.get(M.ItemStatus.INGESTED, 0),
        "duplicate": by_status.get(M.ItemStatus.DUPLICATE, 0),
        "failed": by_status.get(M.ItemStatus.FAILED, 0),
        "started_at": job["started_at"], "finished_at": job["finished_at"],
        "percent": round(100.0 * done / job["total"], 1) if job["total"] else 0.0,
    }


def failed_items(store: Store, job_id: str, limit: int = 100) -> list[dict]:
    """Files that could not be ingested, with the reason for each."""
    return store.q(
        "SELECT display_name, path, error FROM ingest_items "
        "WHERE job_id = ? AND status = ? ORDER BY ordinal LIMIT ?",
        (job_id, M.ItemStatus.FAILED, limit))
