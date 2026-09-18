# CARETRACE bulk ingestion — measured

Every number here is produced by `bench_bulk.py` and rendered by
`report_bulk.py` from `bench_results.json`. Nothing is a projection and
nothing is typed by hand. Re-run both to regenerate.

Machine: Darwin arm64, Python 3.13.15.

## Corpus

- **10,000 files**, 3.6 MB, 400 synthetic patients
- generated in 1.97s
- entirely fictional; no real patient data

Composition — the awkward cases are deliberate:

| Document kind | Files |
|---|---|
| LAB_REPORT | 4,112 |
| CONSULTATION | 1,538 |
| PRESCRIPTION | 1,370 |
| IMAGING_REPORT | 1,203 |
| PATHOLOGY_REPORT | 959 |
| ECG_REPORT | 558 |
| DUPLICATE | 202 |
| CORRUPT | 58 |

`DUPLICATE` files are byte-identical resubmissions; `CORRUPT` files claim
to be PDFs and are not. An ingester that has met neither has not been
measured on anything resembling a real corpus.

## Result at 10,000 files

- **9,740 ingested**, 202 reported as
  duplicates, 58 recorded as failures
- 9,740 pages of raw text retained
- **1.13s wall**, 8,862.1 docs/s
- database 29.2 MB, peak RSS 110.2 MB

Not one of the 58 unreadable files failed the batch. Each is
a FAILED item carrying the parser's own exception text, reviewable through
the job endpoint.

## Worker sweep — the pool makes it slower

The design parses in a thread pool and writes serially. Each configuration
was run 5 times and the median is reported, with
the spread across runs, because single-shot timings were order-dependent
enough to invert this conclusion:

| Workers | Wall (s) | docs/s (median) | Spread | DB (MB) | Peak RSS (MB) |
|---|---|---|---|---|---|
| 1 | 1.13 | 8862.1 | 10.2% | 29.2 | 110.2 |
| 2 | 1.25 | 7994.1 | 4.1% | 29.2 | 119.6 |
| 4 | 1.42 | 7019.5 | 1.2% | 29.2 | 125.6 |
| 8 | 1.68 | 5957.2 | 6.3% | 29.2 | 127.8 |

Throughput declines monotonically: 8,862.1 docs/s on one
worker down to 5,957.2 on 8, a 33% loss that clears
the 10.2% worst within-configuration spread by a wide margin.
The serialized SQLite writer is the whole cost here and parsing a small
text file is nearly free, so additional threads only add coordination.

### The same holds for PDFs

PDFs are the case the pool was added for — 400 distinct
synthetic PDFs, 0.6 MB:

| Workers | Wall (s) | docs/s |
|---|---|---|
| 1 | 0.27 | 1489.0 |
| 2 | 0.28 | 1454.3 |
| 4 | 0.28 | 1430.0 |
| 8 | 0.29 | 1391.7 |

Throughput falls from 1,489.0 docs/s on one worker to
1,391.7 on 8. PDF parsing costs roughly 6x more per file
than text, and is still no faster in parallel.

### Why: the parser holds the GIL

Parsing 150 PDFs of 4 pages each,
serially and then pooled (111.8 files/s serial):

| Threads | Wall (s) | files/s | Speedup |
|---|---|---|---|
| 2 | 1.36 | 109.9 | 0.98 |
| 4 | 1.34 | 112.0 | 1.0 |
| 8 | 1.35 | 110.9 | 0.99 |

`pypdf`'s text extraction is pure Python, so it holds the GIL for its
duration and threads cannot parallelise it. This is a property of the
parser, not of the ingester.

A process pool would sidestep the GIL. It could not be measured here
(unavailable here: PermissionError), so no figure is reported and none is claimed.

**Consequence:** the default is one worker. The pool is kept because it
costs nothing at one worker and is the seam where a GIL-releasing
parser or an I/O-bound OCR service parallelises for free. A speedup
this ingester does not deliver is not advertised.

## Transaction size

| Chunk | Wall (s) | docs/s |
|---|---|---|
| 50 | 1.22 | 8164.7 |
| 200 | 1.19 | 8404.5 |
| 800 | 1.01 | 9921.6 |

One transaction per chunk. Per-file commits would make fsync the
bottleneck; a single transaction for the whole batch would put 10,000
files at risk of one failure and make resumption meaningless.

## Resumability

A job is interrupted mid-run and re-run. What must hold is that resuming
processes only what was left and writes no document twice:

- planned: 250 items
- interrupted after 75 items (72 documents committed)
- resumed run processed 175 items
- final: 250/250 items, status COMPLETED
- documents in the case: 240 (no duplicate rows from the restart)

This works because an item's terminal status is written in the same
transaction as the document rows it produced. An item still PENDING after
a crash committed nothing, so re-running it is safe by construction.

## What is not measured here

- **Process-pool parsing** — unavailable in this environment.
- **OCR throughput** — no OCR engine ships with this build; see the OCR
  interface section of the README.
- **Concurrent ingestion into one case from several processes.** SQLite
  permits one writer; the job model would serialize them, untested.
- **Corpora larger than 10,000 files.** RSS was flat (~110.2 MB) because
  parsing is chunked, so nothing suggests a ceiling, but it is unmeasured.

