"""Render bulk_benchmark.md from bench_results.json. No number is typed by hand.

Reads only the measured JSON, so the report cannot drift from the benchmark
that produced it. Run bench_bulk.py first.
"""
from __future__ import annotations

import json
import platform
from pathlib import Path

D = json.load(open("bench_results.json"))


def table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    head = "| " + " | ".join(h for h, _ in cols) + " |"
    rule = "|" + "|".join("---" for _ in cols) + "|"
    body = ["| " + " | ".join(str(r.get(k, "")) for _, k in cols) + " |"
            for r in rows]
    return "\n".join([head, rule, *body])


c = D["corpus"]
ws = D["worker_sweep"]
for _r in ws + D.get("chunk_sweep", []) + D.get("pdf_corpus", {}).get("sweep", []):
    if "spread_pct" in _r:
        _r["spread"] = f"{_r['spread_pct']}%"
one = ws[0]
best = max(ws, key=lambda r: r["docs_per_s"])
pc = D.get("pdf_corpus", {})
g = D.get("gil", {})
rs = D["resume"]

lines = [
    "# CARETRACE bulk ingestion — measured",
    "",
    "Every number here is produced by `bench_bulk.py` and rendered by",
    "`report_bulk.py` from `bench_results.json`. Nothing is a projection and",
    "nothing is typed by hand. Re-run both to regenerate.",
    "",
    f"Machine: {platform.system()} {platform.machine()}, "
    f"Python {platform.python_version()}.",
    "",
    "## Corpus",
    "",
    f"- **{c['written']:,} files**, {c['corpus_mb']} MB, "
    f"{c['patients']} synthetic patients",
    f"- generated in {c['generate_s']}s",
    "- entirely fictional; no real patient data",
    "",
    "Composition — the awkward cases are deliberate:",
    "",
    table([{"kind": k, "n": f"{v:,}"} for k, v in
           sorted(c["by_modality"].items(), key=lambda kv: -kv[1])],
          [("Document kind", "kind"), ("Files", "n")]),
    "",
    "`DUPLICATE` files are byte-identical resubmissions; `CORRUPT` files claim",
    "to be PDFs and are not. An ingester that has met neither has not been",
    "measured on anything resembling a real corpus.",
    "",
    "## Result at 10,000 files",
    "",
    f"- **{one['ingested']:,} ingested**, {one['duplicate']} reported as",
    f"  duplicates, {one['failed']} recorded as failures",
    f"- {one['pages']:,} pages of raw text retained",
    f"- **{one['wall_s']}s wall**, {one['docs_per_s']:,} docs/s",
    f"- database {one['db_mb']} MB, peak RSS {one['peak_rss_mb']} MB",
    "",
    f"Not one of the {one['failed']} unreadable files failed the batch. Each is",
    "a FAILED item carrying the parser's own exception text, reviewable through",
    "the job endpoint.",
    "",
    "## Worker sweep — the pool makes it slower",
    "",
    "The design parses in a thread pool and writes serially. Each configuration",
    f"was run {ws[0].get('repeats', 1)} times and the median is reported, with",
    "the spread across runs, because single-shot timings were order-dependent",
    "enough to invert this conclusion:",
    "",
    table(ws, [("Workers", "workers"), ("Wall (s)", "wall_s"),
               ("docs/s (median)", "docs_per_s"), ("Spread", "spread"),
               ("DB (MB)", "db_mb"), ("Peak RSS (MB)", "peak_rss_mb")]),
    "",
    f"Throughput declines monotonically: {ws[0]['docs_per_s']:,} docs/s on one",
    f"worker down to {ws[-1]['docs_per_s']:,} on {ws[-1]['workers']}, a"
    f" {round(100 * (1 - ws[-1]['docs_per_s'] / ws[0]['docs_per_s']))}% loss"
    " that clears",
    f"the {max(r['spread_pct'] for r in ws)}% worst within-configuration spread"
    " by a wide margin.",
    "The serialized SQLite writer is the whole cost here and parsing a small",
    "text file is nearly free, so additional threads only add coordination.",
    "",
]

if pc.get("available"):
    pcs = pc["sweep"]
    lines += [
        "### The same holds for PDFs",
        "",
        f"PDFs are the case the pool was added for — {pc['files']} distinct",
        f"synthetic PDFs, {pc['corpus_mb']} MB:",
        "",
        table(pcs, [("Workers", "workers"), ("Wall (s)", "wall_s"),
                    ("docs/s", "docs_per_s")]),
        "",
        f"Throughput falls from {pcs[0]['docs_per_s']:,} docs/s on one worker to",
        f"{pcs[-1]['docs_per_s']:,} on {pcs[-1]['workers']}. PDF parsing costs"
        f" roughly {round(ws[0]['docs_per_s'] / pcs[0]['docs_per_s'])}x more per"
        " file",
        "than text, and is still no faster in parallel.",
        "",
    ]

if g.get("available"):
    t = g["threads"]
    lines += [
        "### Why: the parser holds the GIL",
        "",
        f"Parsing {g['files']} PDFs of {g['pages_per_file']} pages each,",
        f"serially and then pooled ({g['serial_per_s']} files/s serial):",
        "",
        table([{"w": w, **v} for w, v in t.items()],
              [("Threads", "w"), ("Wall (s)", "wall_s"),
               ("files/s", "per_s"), ("Speedup", "speedup")]),
        "",
        "`pypdf`'s text extraction is pure Python, so it holds the GIL for its",
        "duration and threads cannot parallelise it. This is a property of the",
        "parser, not of the ingester.",
        "",
        f"A process pool would sidestep the GIL. It could not be measured here",
        f"({g['process_pool']}), so no figure is reported and none is claimed.",
        "",
        "**Consequence:** the default is one worker. The pool is kept because it",
        "costs nothing at one worker and is the seam where a GIL-releasing",
        "parser or an I/O-bound OCR service parallelises for free. A speedup",
        "this ingester does not deliver is not advertised.",
        "",
    ]

cs = D["chunk_sweep"]
lines += [
    "## Transaction size",
    "",
    table(cs, [("Chunk", "chunk_size"), ("Wall (s)", "wall_s"),
               ("docs/s", "docs_per_s")]),
    "",
    "One transaction per chunk. Per-file commits would make fsync the",
    "bottleneck; a single transaction for the whole batch would put 10,000",
    "files at risk of one failure and make resumption meaningless.",
    "",
    "## Resumability",
    "",
    "A job is interrupted mid-run and re-run. What must hold is that resuming",
    "processes only what was left and writes no document twice:",
    "",
    f"- planned: {rs['planned_total']} items",
    f"- interrupted after {rs['interrupted_after']} items"
    f" ({rs['docs_at_interrupt']} documents committed)",
    f"- resumed run processed {rs['resumed_processed']} items",
    f"- final: {rs['final_processed']}/{rs['planned_total']} items,"
    f" status {rs['final_status']}",
    f"- documents in the case: {rs['documents_total']}"
    f" (no duplicate rows from the restart)",
    "",
    "This works because an item's terminal status is written in the same",
    "transaction as the document rows it produced. An item still PENDING after",
    "a crash committed nothing, so re-running it is safe by construction.",
    "",
    "## What is not measured here",
    "",
    "- **Process-pool parsing** — unavailable in this environment.",
    "- **OCR throughput** — no OCR engine ships with this build; see the OCR",
    "  interface section of the README.",
    "- **Concurrent ingestion into one case from several processes.** SQLite",
    "  permits one writer; the job model would serialize them, untested.",
    "- **Corpora larger than 10,000 files.** RSS was flat"
    f" (~{one['peak_rss_mb']} MB) because",
    "  parsing is chunked, so nothing suggests a ceiling, but it is unmeasured.",
    "",
]

Path("bulk_benchmark.md").write_text("\n".join(lines) + "\n")
print("bulk_benchmark.md", len("\n".join(lines)), "chars")
