<!-- Public repo README. In the published repo this file is named README.md. -->

# CARETRACE (core)

CARETRACE reads fragmented medical records and builds an audit trail across them.
It pulls out the facts a document states, separates them from the claims a
document makes, and then checks those against each other: what changed between
reports, what two reports disagree on, and what a claim relies on but never
actually shows up in the records. Every fact it keeps points back to the page
and the exact text it came from.

The important part is what it does *not* do. It doesn't diagnose, it doesn't
recommend treatment, and when two sources disagree it does not quietly pick one.
It records the disagreement and leaves it open for a person to resolve. All of
the reconciliation logic is deterministic — same input, same output, no model in
the loop.

This repository holds the reasoning core only. The demonstration case included
here is fictional.

> This is an early research prototype. It has not been clinically validated and
> must not be used to make decisions about a real patient. Please read
> [DISCLAIMER.md](DISCLAIMER.md).

## What's here

The core is a small, self-contained TypeScript package with no runtime
dependencies (the one listed dependency, `drizzle-orm`, is only used by the
database schema types).

- `lib/evidence-engine.ts` — the reconciliation logic: change detection,
  numeric / status / medication conflicts, evidence gaps, relationships and the
  timeline.
- `lib/evidence-packs.ts` — the medical signatures the engine reasons with. They
  are generic; nothing here is tied to a particular lab or report layout.
- `lib/types.ts` — the data model everything else is built on.
- `lib/case-audit.ts` — runs the engine over a single case.
- `lib/demo-data.ts` — the fictional 12-document case used by the tests.
- `lib/terminology/` — the built-in concept matching (core seed + lookup).
- `db/schema.ts`, `drizzle/` — the evidence/provenance schema and its migrations.
- `caretrace/` — an earlier Python reference of the same ideas.

The user interface, storage, OCR/layout service, hospital multi-tenancy, and the
FHIR/HL7 work are not in this repository. See "Getting the full system" below.

## Running it

You need Node 22.13 or newer.

```bash
npm install
npm test          # runs the engine over the fictional case and checks the results
npm run typecheck # type-checks the whole core
```

`npm test` exercises change, conflict and gap detection against the demo case
without needing a database or any external service, so it's the quickest way to
see what the engine actually produces.

For a full walkthrough — how the engine thinks, how to read an audit result, how
to run it in your own script, and how to point it at your own data — see
[USAGE.md](USAGE.md).

## Getting the full system

The complete application — UI and integrations — isn't open. I'm sharing it for
evaluation and contribution under a signed NDA. If you want to test it, or you
work with a hospital or public-health body that wants to trial it in a
non-production setting, open a discussion or get in touch. There's more on how
that works in [LEGAL_NDA_CLA.md](LEGAL_NDA_CLA.md).

A note on deployment: I'd like CARETRACE to eventually be free for public and
government hospitals. It isn't ready for live care yet, and I won't pretend
otherwise. The realistic path is shadow-mode pilots — running it alongside an
existing process, never in place of one — while the accuracy work and any
regulatory steps happen.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[code of conduct](CODE_OF_CONDUCT.md). If you find a security issue, please
report it privately — [SECURITY.md](SECURITY.md) explains how. Never put real
patient data into an issue, a pull request, or a test.

## License

AGPL-3.0-only. See [LICENSE](LICENSE). In short: if you run a modified version of
this as a network service, you have to make your changes available to its users
under the same license.

Copyright © 2026 Koushik Das.
