# CARETRACE

**Evidence audit for fragmented medical records.**

Turn scattered medical records into an auditable evidence map. CARETRACE extracts
documented facts, connects related evidence, identifies changes and contradictions,
exposes missing information, and preserves source provenance.

> Research/prototype software. Not a diagnostic or treatment system, and not clinically
> validated. All demo patient data is synthetic.

## The product principle

Evidence first. Provenance always. Conflicts exposed. Missing evidence explicitly
represented. No guessing.

When two documents disagree, CARETRACE does **not** pick a winner. It reports both
values with their sources and marks the finding UNRESOLVED. When a claim's declared
supporting evidence is not in the records, CARETRACE says the evidence was not
located — never that the claim is false.

## Run it

```bash
pip install -r requirements.txt
PYTHONPATH=. uvicorn caretrace.api.app:app --reload
# open http://127.0.0.1:8000
```

Then: **Open Demo Case** → **Run Evidence Audit**.

There is also a single-file offline build that needs no server:

```bash
PYTHONPATH=. python build_offline.py   # writes caretrace_demo.html
open caretrace_demo.html
```

## Verify it

```bash
PYTHONPATH=. python -m pytest tests/ -q   # 51 tests
PYTHONPATH=. python verify.py             # regenerates verification_report.md
node tests/render_check.js caretrace_demo.html   # every route renders (needs jsdom)
```

`verify.py` evaluates each acceptance criterion as a predicate against live engine
output and exits non-zero on failure, so `verification_report.md` cannot drift from
the system it describes.

## What the demo case demonstrates

Case `CT-DEMO-001` (synthetic, 12 documents) is built to exercise each detector:

| Finding | What the engine does |
| --- | --- |
| Hb 8.7 vs 12.1 g/dL, one day apart | Numeric conflict, UNRESOLVED, both sources cited across all 4 restatements |
| Platelets 186 vs 402 ×10⁹/L | Second numeric conflict on the same episode |
| Ferrous sulfate active in prescription, absent from later medication list | Medication documentation conflict — no inference that it was stopped |
| "Iron deficiency confirmed" (Feb), ferritin drawn in Apr | Evidence gap: the later result cannot support the earlier claim, and the gap says so explicitly |
| Discharge summary cites a CT report | Missing source — referenced document not in the records |
| `10_Referral_Letter.pdf` | Extraction incomplete, flagged for review rather than silently dropped |
| Same Hb restated in several documents | Duplicate relationships, not counted as changes |

## Architecture

```
CARETRACE CORE
├── Document Engine      ingestion, classification, page text
├── Evidence Engine      facts, claims, medications, events
├── Provenance Engine    every finding → fact → document → page → source text
├── Relationship Engine  SUPPORTS / CONTRADICTS / DUPLICATES / CHANGED_FROM ...
├── Conflict Engine      numeric + medication conflict detection
├── Timeline / Graph     chronological ordering and graph projection (api/views.py)
└── Audit Engine         changes, gaps, metrics, brief
        └── Medical Pack  concept lexicon, claim evidence requirements, thresholds
```

The domain knowledge — which lab concepts exist, their aliases, materiality
thresholds, and what evidence each claim type requires — lives in
`caretrace/packs/medical/`. The core is pack-agnostic, so a laboratory, imaging, or
research pack can be added without touching the engines.

**The audit logic is deterministic.** No LLM is involved in comparison, conflict
detection, or gap detection. Extraction is modular (`caretrace/core/extract.py`); an
OCR backend can be substituted behind the same interface without affecting the audit.

### Pipeline

```
INGEST → CLASSIFY → EXTRACT → NORMALIZE → CREATE_FACTS → CREATE_CLAIMS →
CREATE_EVENTS → RESOLVE_ENTITIES → DETECT_CHANGES → DETECT_CONFLICTS →
RESOLVE_CLAIMS → BUILD_RELATIONSHIPS → DETECT_GAPS → GENERATE_AUDIT
```

Each stage reports its own counts, surfaced live in the Processing view.

## Layout

```
caretrace/
  core/          schema.sql, models, store, pipeline, extraction
  core/engine/   changes, conflicts, claims_engine, gaps
  packs/medical/ lexicon (concepts, aliases, thresholds, claim requirements)
  packs/         laboratory, imaging, cardiology, neurophysiology, molecular
  terminology/   optional vocabulary providers (RxNorm, LOINC, SNOMED, ICD-11)
  api/           FastAPI app + REST views
  demo/          synthetic case builder + generated PDFs
  web/           SPA (vanilla JS, no build step, no CDN)
tests/           unit, API and DOM-render tests
uiharness/       renders every screen in jsdom against captured API responses
verify.py        regenerates verification_report.md
build_offline.py bundles the SPA + audited case into one HTML file
```

## API

```
POST /api/demo                     create + populate the synthetic case
POST /api/cases/:id/process        run the pipeline
GET  /api/cases/:id                case + computed metrics
GET  /api/cases/:id/facts          extracted facts
GET  /api/cases/:id/claims         claims with evidence status
GET  /api/cases/:id/medications    medications with documented status
GET  /api/cases/:id/conflicts      conflicts with both sides and full provenance
GET  /api/cases/:id/evidence-gaps  gaps with basis text
GET  /api/cases/:id/changes        documented changes
GET  /api/cases/:id/series         per-concept numeric series for charting
GET  /api/cases/:id/timeline       chronological entries grouped by date
GET  /api/cases/:id/graph          nodes + edges for the evidence graph
GET  /api/cases/:id/brief          final evidence brief
GET  /api/cases/:id/run            latest processing run + stage counts
GET  /api/sources/:id              source document, page, and extracted text
GET  /api/documents/:id/file       original uploaded file
GET  /api/cases/:id/codings        advisory vocabulary annotations
GET  /api/terminology/providers    live provider status and licence position
GET  /api/terminology/config       which credential fields are set (never values)
DELETE /api/cases/:id              delete a case and everything derived from it
```

## Patient registry

A case is a folder of documents, and nothing guarantees they all belong to one
person. The registry stage reads the identity each document *states* — name,
date of birth, sex, record number — records it as an assertion, and then
decides which patient record it belongs to.

Two rules attach a document: an exact institution-issued record number, or a
full demographic match (name plus date of birth, corroborated by sex where
stated). Anything weaker, anything ambiguous, and anything contradictory is
queued for review with its candidates listed.

The asymmetry is deliberate. A missed merge leaves a document in a queue a
human looks at. A wrong merge produces a record that is internally consistent,
fully provenanced, and describes a person who does not exist — and the audit
engine downstream would find nothing to disagree with, because every fact in it
is genuine. So every ambiguous case refuses, and the UI offers no merge button:
deciding two records are the same person outlives the session.

Resolution changes what the audit compares. Detection runs **per patient** —
handing a detector the union of two people's records would manufacture changes
and conflicts out of two normal histories. On a single-patient corpus this
partitioning is a no-op, and `verify.py` checks that: the audit metrics are
identical to the pre-registry baseline.

Institutions and clinicians are extracted alongside, from letterhead and
recognised header fields. Attribution is best-effort and the **document remains
the provenance anchor** — no audit result depends on it. Affiliation is inferred
only from roles a letterhead genuinely implies: a clinician named as *ordering*
on a laboratory report asked for the test, which says nothing about where they
work, so that field stays empty rather than borrowing the nearest letterhead.

## Bulk ingestion

`POST /api/cases/{id}/ingest/bulk?source=<dir|archive>` ingests a directory or
archive and returns **202** with a job id. Progress is polled at
`GET /api/ingest/jobs/{job_id}`, which returns the counts *and* the failure
list — a batch that silently dropped files is the failure mode worth designing
against, so failures are never hidden behind a second call.

Each item's terminal status is committed in the same transaction as the document
rows it produced. An interrupted run therefore leaves no half-ingested file, and
re-running the job processes exactly the remainder. Resume granularity is the
chunk (default 200 files), not the individual file.

Byte-identical resubmissions are recognised by content hash and recorded as
duplicates rather than ingested twice. Unreadable files become FAILED items
carrying the parser's own exception text; they never end the batch.

### Measured, not projected

`bench_bulk.py` builds a synthetic corpus, runs the sweep, and writes
`bench_results.json`; `report_bulk.py` renders `bulk_benchmark.md` and
`bulk_throughput.png` from it. No number in either is typed by hand.

At 10,000 files the measured rate is **8,862 docs/s** on one
worker. The thread pool does not help — throughput *declines* monotonically to
5,957 docs/s at 8 workers, on PDFs as well as
text. The cause is measured rather than assumed: `pypdf`'s text extraction is
pure Python and holds the GIL, so threaded parsing runs at 0.98–1.00x serial.
`DEFAULT_WORKERS` is therefore **1**. The pool is retained because it costs
nothing at that setting and is the seam where a lock-releasing parser or an
out-of-process OCR service would parallelise; a process pool was not measurable
in the development sandbox and so is not claimed.

## Terminology (optional)

CARETRACE normalizes concepts using its own packs. The terminology layer adds
*advisory* links from a document's wording to a published vocabulary concept —
RxNorm for medications, LOINC for observations, SNOMED CT for findings, ICD-11
for diagnosis statements.

Two properties are enforced by tests rather than convention:

1. **The audit never depends on it.** Conflict, change and gap detection read
   the packs' own concepts. Processing a case with every provider unreachable
   produces byte-identical audit counts — `test_audit_is_identical_offline`.
2. **An approximate match is never asserted.** A coding carries its match kind;
   only exact and synonym matches are marked assertable. A fuzzy hit is shown as
   `UNRESOLVED`, never silently treated as the concept.

No vocabulary content ships with CARETRACE. RxNorm is public domain and works
out of the box; LOINC, SNOMED CT and ICD-11 are licence-gated, so the deployment
supplies credentials and CARETRACE queries the publisher's own service. Absent
credentials, a provider reports `UNLICENSED` on the Terminology screen and
coverage drops — the audit does not.

```bash
export CARETRACE_LOINC_USERNAME=... CARETRACE_LOINC_PASSWORD=...
export CARETRACE_TERMINOLOGY_OFFLINE=1   # forbid all outbound lookups
```

Credentials are read from the environment and never returned by the API; the
admin screen shows only whether each field is set.

## Deliberate scope limits

Not built (extension points exist): full medical ontology, FHIR, EHR integration,
clinical decision support, risk scoring, multi-tenancy, OCR backend. The MVP is a
small, polished evidence-audit core rather than a broad, shallow platform.
