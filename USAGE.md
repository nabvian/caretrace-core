# Using and testing CARETRACE (core)

This guide walks through installing the open core, running it, reading what it
produces, and pointing it at your own data. It covers the TypeScript core in this
repository and the Python reference under `caretrace/`.

Before anything else: CARETRACE is an unvalidated research prototype and is not
for clinical use. See [DISCLAIMER.md](DISCLAIMER.md).

---

## 1. What you need

- **Node.js 22.13 or newer** (`node --version`). The core uses recent language
  features, so older Node will fail.
- That's it for the TypeScript core — no database, no cloud account, no OCR
  service. The Python reference (section 9) needs Python 3.11+ if you want it.

## 2. Install

```bash
git clone https://github.com/<your-account>/caretrace-core.git
cd caretrace-core
npm install
```

`npm install` pulls a small dev toolchain (TypeScript, tsx) plus `drizzle-orm`,
which is only used by the database schema types. The reasoning engine itself has
no runtime dependencies.

## 3. Run it

```bash
npm test          # run the engine over the built-in fictional case
npm run typecheck # type-check the whole core with tsc
```

`npm test` runs the engine against a 12-document **fictional** case and checks
its results. You should see:

```
CARETRACE core — deterministic engine
  ok  runEvidenceAudit() reproduces the published demo metrics
  ok  the audit is deterministic (two runs are identical)
  ok  exported demoAudit matches a fresh run
  ok  every conflict is left UNRESOLVED (the engine never picks a winner)
  ok  traceability is a percentage in [0, 100]
  ok  buildCaseAudit() on an empty case yields zeroed metrics, not a crash
  6 passing
```

If those pass, the engine works on your machine.

## 4. How CARETRACE thinks

The whole system is built on one idea: **keep evidence and reasoning separate,
and never throw away a source.**

Documents are turned into small, dated, source-linked pieces of evidence:

- **Facts** — something a document *measured* (a number or a status), e.g.
  "heart rate 96 /min on 2026-02-01, page 1 of the ECG report".
- **Claims** — something a document *asserts* (a finding, impression, diagnosis),
  e.g. "iron deficiency confirmed".
- **Medications** — a documented drug entry with its status (active / inactive /
  not listed).

The engine then reasons over that evidence, deterministically:

- **Changes** — the same measurement, different values, on different dates.
- **Conflicts** — sources that disagree within the same short clinical episode.
  Numeric, status, and medication conflicts each have their own rule.
- **Evidence gaps** — a claim whose declared supporting evidence, referenced
  document, or expected follow-up isn't in the records.
- **Relationships** — typed links (supports, contradicts, duplicates, changed-to,
  missing-support) with a written rationale.
- **Timeline** — the documents ordered by their clinical date.

Two rules are absolute:

1. **It never picks a winner.** When two sources disagree, the conflict is
   recorded with *both* sides and their provenance and marked `UNRESOLVED`. A
   human resolves it, not the engine.
2. **Absence is not falsehood.** If a claim's supporting evidence isn't found, the
   engine says the evidence "was not located" — never that the claim is false. A
   drug missing from a later list is not treated as stopped.

There is no model in this loop. Same input, same output, every time.

## 5. Reading an audit result

Every audit returns an `AuditResult` (see `lib/types.ts`). The quickest summary
is `.metrics`:

```json
{
  "documents": 12, "facts": 42, "claims": 9, "medications": 5,
  "changes": 7, "conflicts": 4, "gaps": 3,
  "unresolved": 7, "traceability": 100
}
```

`traceability` is the percentage of evidence items that carry a full source link
(document + page + text). A conflict looks like this:

```jsonc
{
  "kind": "NUMERIC",
  "concept": "heart_rate",
  "status": "UNRESOLVED",
  "evidenceA": { "value": 72, "unit": "/min", "sourceDocument": "ECG 1", "sourcePage": 1 },
  "evidenceB": { "value": 96, "unit": "/min", "sourceDocument": "ECG 2", "sourcePage": 1 },
  "materialityBasis": "8 /min absolute or 12% relative",
  "explanation": "Source documents record materially different heart_rate values within the same 1-day clinical episode..."
}
```

Both readings are kept, both point back to their document and page, and neither
is chosen.

## 6. Run the engine in your own script

The built-in case is exposed directly:

```ts
// demo.ts  →  run with: npx tsx demo.ts
import { runEvidenceAudit } from "./lib/evidence-engine";

const audit = runEvidenceAudit();
console.log(audit.metrics);
for (const c of audit.conflicts) {
  console.log(c.displayId, c.concept, "→", c.explanation);
}
```

## 7. Test it with your own data

The entry point for arbitrary data is `buildCaseAudit()` in `lib/case-audit.ts`:

```ts
buildCaseAudit(caseRecord, documents, facts, claims, medications, documentReferences, events)
```

Everything after `documents` is optional. You hand it evidence you've already
extracted; it runs every detector and returns the same `AuditResult`.

Here's a minimal, self-contained example that produces one numeric conflict.
Save it as `mycase.ts` and run `npx tsx mycase.ts`.

```ts
import { buildCaseAudit } from "./lib/case-audit";
import type { CaseRecord, Fact, MedicalDocument } from "./lib/types";

// A small helper so we don't repeat the required scaffolding on every fact.
function fact(partial: Partial<Fact> & Pick<Fact, "id" | "concept" | "value" | "date" | "sourceDocumentId" | "sourceDocument" | "sourcePage" | "sourceText">): Fact {
  return {
    displayId: partial.id,
    originalConcept: partial.concept,
    unit: "/min",
    datePrecision: "day",
    confidence: 1,
    type: "OBSERVATION",
    terminology: { caretraceId: `caretrace:${partial.concept}`, sourceText: partial.sourceText, matchType: "EXACT", terminologySource: "caretrace_core", sourceCode: partial.concept, sourceVersion: "0", sourceUri: "", checksumVerified: null },
    temporal: { eventDate: partial.date, dateType: "report", precision: "day", status: "EXPLICIT", sourcePage: partial.sourcePage, sourceText: partial.sourceText, confidence: "explicit" },
    ...partial,
  } as Fact;
}

const caseRecord: CaseRecord = {
  id: "case-1", caseCode: "CASE-1", patientName: "Test Patient",
  dob: null, address: null, contactNumber: null, email: null,
  lifecycleState: "AUDIT_REQUIRED", lifecycleUpdatedAt: "2026-02-01",
  synthetic: false, createdAt: "2026-02-01",
};

const doc = (id: string, name: string): MedicalDocument => ({
  id, name, type: "CARDIOLOGY_REPORT", date: "2026-02-01", pages: 1,
  uploadStatus: "UPLOADED", processingStatus: "PROCESSED", pageText: { 1: "" },
});
const documents = [doc("d1", "ECG 1"), doc("d2", "ECG 2")];

const facts = [
  fact({ id: "f1", concept: "heart_rate", value: 72, date: "2026-02-01", sourceDocumentId: "d1", sourceDocument: "ECG 1", sourcePage: 1, sourceText: "HR 72 /min" }),
  fact({ id: "f2", concept: "heart_rate", value: 96, date: "2026-02-01", sourceDocumentId: "d2", sourceDocument: "ECG 2", sourcePage: 1, sourceText: "HR 96 /min" }),
];

const audit = buildCaseAudit(caseRecord, documents, facts);
console.log(audit.metrics);            // conflicts: 1
console.log(audit.conflicts[0].explanation);
```

### What makes each detector fire

The detectors are picky on purpose — that's what keeps the output trustworthy.
The thresholds live in `lib/evidence-packs.ts`, per concept.

- **Numeric conflict** — two facts, same `concept`, numeric `value`,
  `datePrecision: "day"`, within the concept's episode window, differing by more
  than its materiality threshold, and coming from **two different documents**.
  (Heart rate above: 72 vs 96 is a 24 /min gap, threshold is 8, same day, two
  docs → one conflict.)
- **Status conflict** — string-valued facts for a concept that has a status rule
  (e.g. `rhythm`, `consolidation`), with mutually exclusive value classes in the
  same episode, from two documents.
- **Medication conflict** — same `normalizedDrug` and `date`, one entry `ACTIVE`
  and another `INACTIVE` or `NOT_LISTED`.
- **Change** — numeric facts for one concept with `temporal.status: "EXPLICIT"`,
  different dates further apart than the episode window, different values, same
  unit.
- **Evidence gap** — a claim with `gapRule: "MISSING_SUPPORT"`, a list of
  `supportConcepts`, and an `evidenceLookbackDays` window, where no qualifying
  fact is found on or before the claim within that window.

If a concept isn't in the packs, numeric comparison falls back to "any
difference is material" and the episode window is 0 days. Add your own concepts
by editing `lib/evidence-packs.ts`.

## 8. Where to look in the code

- `lib/types.ts` — every data shape referenced above.
- `lib/evidence-engine.ts` — the detectors, ~100 lines, readable top to bottom.
- `lib/evidence-packs.ts` — concepts, aliases, thresholds, episode windows.
- `lib/demo-data.ts` — the fictional case, and a good template for building your own.
- `test/engine.test.ts` — how the engine is exercised.

## 9. The Python reference

`caretrace/` holds an earlier, self-contained Python implementation of the same
ideas, with its own web UI, tests, and a benchmark harness. It's useful for
comparing behaviour. From inside `caretrace/`:

```bash
pip install -r requirements.txt
PYTHONPATH=. uvicorn caretrace.api.app:app --reload   # then open http://127.0.0.1:8000
PYTHONPATH=. python -m pytest tests/ -q               # run its test suite
PYTHONPATH=. python verify.py                         # regenerate verification_report.md
```

Full details are in [`caretrace/README.md`](caretrace/README.md).

## 10. What CARETRACE does not do

It does not diagnose, does not recommend treatment, does not score risk, and does
not resolve conflicts for you. It has no clinical validation. Treat every output
as something a qualified person must check.

## 11. The full system

This repository is the reasoning core. The user interface, storage, OCR/layout
service, hospital multi-tenancy, and FHIR/HL7 interoperability are kept in a
separate private repository, available for evaluation and contribution under a
signed NDA. See [LEGAL_NDA_CLA.md](LEGAL_NDA_CLA.md).

If you work with a hospital or public-health body that wants to trial it in a
non-production, shadow-mode setting, open a discussion or get in touch.

## 12. Troubleshooting

- **`npm test` fails immediately with a syntax error** — you're on old Node. Use
  22.13+.
- **`tsx: command not found`** — run `npm install` first; `tsx` is a dev
  dependency, invoke it with `npx tsx` or the npm scripts.
- **Type errors after editing** — run `npm run typecheck` to see them all; the
  config is `tsconfig.json`.
- **Your data produces no conflicts** — check `datePrecision` is `"day"`, the two
  facts share the exact `concept` string, and they come from two different
  `sourceDocumentId`s within the concept's episode window.

— Koushik Das
