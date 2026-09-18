"""Measure bulk ingestion. Every number in bulk_benchmark.md comes from here.

Run: python bench_bulk.py [--count 10000]

The sweep over worker counts is the point. The module docstring in core/bulk.py
claims throughput scales with workers only until the serialized writer
saturates; a claim like that is worth nothing unless it is measured, so this
finds the actual knee rather than asserting one.
"""
from __future__ import annotations

import argparse
import json
import resource
import statistics
import shutil
import tempfile
import time
from pathlib import Path

from caretrace.core import bulk as B
from caretrace.core import models as M
from caretrace.core.store import Store
from caretrace.demo.synth_corpus import generate


def peak_rss_mb() -> float:
    """Peak resident set size for this process, in MB.

    ru_maxrss is bytes on macOS and kilobytes on Linux; normalising by platform
    rather than guessing keeps the reported figure honest.
    """
    import sys
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


def run_one(corpus: Path, workers: int, chunk_size: int,
            tmp: Path) -> dict:
    """One full ingestion into a fresh database. Returns measured numbers."""
    db = tmp / f"bench_w{workers}_c{chunk_size}.db"
    for suffix in ("", "-wal", "-shm"):
        Path(str(db) + suffix).unlink(missing_ok=True)
    store = Store(db)
    case = store.insert(M.Case(case_ref=f"BENCH-W{workers}",
                               subject_label="synthetic cohort"))
    store.commit()

    job = B.plan_job(store, case.id, corpus, workers=workers,
                     chunk_size=chunk_size)
    t0 = time.perf_counter()
    res = B.run_job(store, job.id)
    wall = time.perf_counter() - t0

    db_bytes = sum(Path(str(db) + s).stat().st_size
                   for s in ("", "-wal", "-shm")
                   if Path(str(db) + s).exists())
    pages = store.q1("SELECT COUNT(*) AS n FROM document_pages")["n"]
    store.conn.close()
    return {
        "workers": workers, "chunk_size": chunk_size,
        "files": job.total, "ingested": res["ingested"],
        "duplicate": res["duplicate"], "failed": res["failed"],
        "pages": pages,
        "wall_s": round(wall, 2),
        "docs_per_s": round(job.total / wall, 1),
        "db_mb": round(db_bytes / (1024 * 1024), 1),
        "peak_rss_mb": round(peak_rss_mb(), 1),
    }


def repeat(corpus: Path, workers: int, chunk_size: int, tmp: Path,
           n: int = 5) -> dict:
    """Run one configuration `n` times and report the median.

    Single-shot timings were order-dependent enough to invert the conclusion:
    a lone run made two workers look 7% faster than one, while five runs each
    show one worker fastest by 14%. Within-configuration spread is reported so
    a reader can judge whether any difference clears the noise.
    """
    runs = [run_one(corpus, workers, chunk_size, tmp) for _ in range(n)]
    rates = sorted(r["docs_per_s"] for r in runs)
    walls = sorted(r["wall_s"] for r in runs)
    med = dict(runs[0])
    med.update({
        "repeats": n,
        "docs_per_s": statistics.median(rates),
        "wall_s": statistics.median(walls),
        "docs_per_s_min": rates[0], "docs_per_s_max": rates[-1],
        "spread_pct": round(100.0 * (rates[-1] - rates[0])
                            / statistics.median(rates), 1),
    })
    return med


def pdf_parse_cost() -> dict:
    """Parse the real demo PDFs, so the .txt figure is not mistaken for PDF.

    A throughput number measured only on plain text would overstate what this
    ingester does on a corpus of scanned reports by a wide margin. Reporting
    both is the honest form.
    """
    from caretrace.demo.render_pdfs import PDF_DIR, render_all
    if not any(PDF_DIR.glob("*.pdf")):
        render_all()
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        return {"available": False}
    t0 = time.perf_counter()
    pages = 0
    from caretrace.core.pipeline import read_pdf_pages
    for p in pdfs:
        try:
            pages += len(read_pdf_pages(p))
        except Exception:                          # noqa: BLE001
            pass
    el = time.perf_counter() - t0
    return {"available": True, "pdfs": len(pdfs), "pages": pages,
            "wall_s": round(el, 3),
            "pdf_per_s": round(len(pdfs) / el, 1) if el else 0.0}


def pdf_corpus_run(tmp: Path, count: int = 400,
                   workers_list=(1, 2, 4, 8)) -> dict:
    """Ingest a corpus of DISTINCT synthetic PDFs and sweep workers.

    This is the case the thread pool exists for. Text files are parsed so
    cheaply that the writer hides any benefit; PDFs cost real work per file,
    so this is where parallel parsing either pays or does not. Each PDF is
    given unique content, because byte-identical files would be caught by
    dedupe and measured as duplicates rather than parses.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return {"available": False,
                "reason": "reportlab not installed; PDF corpus skipped"}

    pdir = tmp / "pdfcorpus"
    pdir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        c = canvas.Canvas(str(pdir / f"{i:05d}_LAB.pdf"), pagesize=A4)
        y = 800
        for line in [
            "MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)",
            f"LABORATORY REPORT  ref {i:05d}",
            f"Patient: Synthetic Person {i % 250}    Sex: M    DOB: 15 May 1988",
            f"MRN: SYN-{200000 + (i % 250)}",
            f"Hemoglobin: {8 + (i % 60) / 10:.1f} g/dL",
            f"Platelets: {150 + i % 200} x10^9/L",
            f"Ferritin: {10 + i % 150} ng/mL",
            "Reported by: Dr. R. Nair",
        ]:
            c.drawString(56, y, line)
            y -= 18
        c.showPage()
        c.save()

    for f in pdir.iterdir():
        f.read_bytes()
    run_one(pdir, 2, 50, tmp)               # warmup, discarded

    sweep = [repeat(pdir, w, B.CHUNK, tmp, n=3) for w in workers_list]
    total_bytes = sum(f.stat().st_size for f in pdir.iterdir())
    shutil.rmtree(pdir, ignore_errors=True)
    return {"available": True, "files": count,
            "corpus_mb": round(total_bytes / (1024 * 1024), 1),
            "sweep": sweep}


def gil_probe(tmp: Path, files: int = 150, pages: int = 4) -> dict:
    """Measure whether threads parallelise PDF text extraction at all.

    The thread pool in core/bulk.py is only worth anything if parsing releases
    the GIL. Rather than assume either way, parse the same corpus serially and
    then through pools of increasing size and report the ratio. A speedup near
    1.0 means the pool is doing nothing for this parser, which is a fact the
    module docstring should state rather than a design intention it should imply.

    A process pool would sidestep the GIL, but ProcessPoolExecutor cannot be
    constructed in the sandbox this was measured in (POSIX semaphores are
    unavailable), so no figure is reported for it and none is claimed.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return {"available": False, "reason": "reportlab not installed"}

    d = tmp / "gilprobe"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(files):
        c = canvas.Canvas(str(d / f"{i:04d}.pdf"), pagesize=A4)
        for _pg in range(pages):
            for j in range(38):
                c.drawString(50, 800 - j * 20,
                             f"Line {j} Hemoglobin {i}.{j}: 9.2 g/dL  "
                             f"MCV 68 fL  Platelets 210 x10^9/L")
            c.showPage()
        c.save()
    paths = sorted(str(p) for p in d.iterdir())
    for p in paths:
        Path(p).read_bytes()

    from caretrace.core.pipeline import read_pdf_pages

    def parse(path: str) -> int:
        return sum(len(t) for t in read_pdf_pages(Path(path)))

    parse(paths[0])                                   # warm the import
    t0 = time.perf_counter()
    for p in paths:
        parse(p)
    serial = time.perf_counter() - t0

    out = {"available": True, "files": files, "pages_per_file": pages,
           "serial_s": round(serial, 2),
           "serial_per_s": round(files / serial, 1), "threads": {}}
    from concurrent.futures import ThreadPoolExecutor
    for w in (2, 4, 8):
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=w) as ex:
            list(ex.map(parse, paths))
        el = time.perf_counter() - t0
        out["threads"][str(w)] = {"wall_s": round(el, 2),
                                  "per_s": round(files / el, 1),
                                  "speedup": round(serial / el, 2)}
    try:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=2):
            pass
        out["process_pool"] = "available but not measured"
    except Exception as exc:                          # noqa: BLE001
        out["process_pool"] = f"unavailable here: {type(exc).__name__}"
    shutil.rmtree(d, ignore_errors=True)
    return out


def resume_check(corpus: Path, tmp: Path) -> dict:
    """Prove resumption: interrupt a job, re-run it, confirm no double-write.

    Simulated by running with a small chunk size, killing the run partway via
    an injected exception, then resuming. What must hold is that the document
    count after resumption equals the count from an uninterrupted run.
    """
    db = tmp / "bench_resume.db"
    for s in ("", "-wal", "-shm"):
        Path(str(db) + s).unlink(missing_ok=True)
    store = Store(db)
    case = store.insert(M.Case(case_ref="BENCH-RESUME",
                               subject_label="synthetic"))
    store.commit()
    job = B.plan_job(store, case.id, corpus, workers=2, chunk_size=25)

    # Interrupt after the first few chunks by raising from the progress hook.
    class Stop(Exception):
        pass

    seen = {"chunks": 0}

    def hook(_p):
        seen["chunks"] += 1
        if seen["chunks"] >= 3:
            raise Stop()

    try:
        B.run_job(store, job.id, progress=hook)
    except Stop:
        pass
    mid = B.job_progress(store, job.id)
    after_interrupt = store.q1("SELECT COUNT(*) AS n FROM documents")["n"]

    res = B.run_job(store, job.id)
    final = B.job_progress(store, job.id)
    total_docs = store.q1("SELECT COUNT(*) AS n FROM documents")["n"]
    store.conn.close()
    return {
        "interrupted_after": mid["processed"],
        "docs_at_interrupt": after_interrupt,
        "resumed_processed": res["ingested"] + res["duplicate"] + res["failed"],
        "final_processed": final["processed"],
        "final_status": final["status"],
        "documents_total": total_docs,
        "planned_total": job.total,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=10_000)
    ap.add_argument("--patients", type=int, default=400)
    ap.add_argument("--workers", type=int, nargs="*",
                    default=[1, 2, 4, 8])
    ap.add_argument("--repeats", type=int, default=5,
                    help="runs per configuration; the median is reported")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="caretrace-bench-"))
    corpus = tmp / "corpus"
    t0 = time.perf_counter()
    gen = generate(corpus, count=args.count, patients=args.patients)
    gen["generate_s"] = round(time.perf_counter() - t0, 2)
    corpus_bytes = sum(p.stat().st_size for p in corpus.iterdir())
    gen["corpus_mb"] = round(corpus_bytes / (1024 * 1024), 1)

    # Warm the filesystem cache before timing anything. Without this the FIRST
    # configuration in the sweep pays for every cold read and the comparison
    # between worker counts measures the page cache rather than the ingester --
    # which showed up as an impossible superlinear speedup.
    for p in corpus.iterdir():
        p.read_bytes()

    # A full discarded run first. Reading the bytes is not enough: the first
    # ingestion also pays one-time costs that belong to no configuration --
    # notably the lazy `import pypdf` triggered by the first unreadable .pdf,
    # which on a short run dominated everything and made one worker look 5x
    # slower than two. A warmup run attributes those costs to nobody.
    warm = tmp / "warmup"
    generate(warm, count=60, patients=5, seed=99)
    run_one(warm, 2, 50, tmp)
    shutil.rmtree(warm, ignore_errors=True)

    sweep = [repeat(corpus, w, B.CHUNK, tmp, n=args.repeats)
             for w in args.workers]
    best = max(sweep, key=lambda r: r["docs_per_s"])
    chunks = [repeat(corpus, best["workers"], c, tmp, n=args.repeats)
              for c in (50, 200, 800)]

    small = tmp / "small"
    generate(small, count=250, patients=20, seed=7)
    out = {
        "corpus": gen,
        "worker_sweep": sweep,
        "chunk_sweep": chunks,
        "pdf": pdf_parse_cost(),
        "pdf_corpus": pdf_corpus_run(tmp),
        "gil": gil_probe(tmp),
        "resume": resume_check(small, tmp),
    }
    (Path("bench_results.json")).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("corpus", "worker_sweep")}, indent=1))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
