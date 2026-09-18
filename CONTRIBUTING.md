# Contributing

Thanks for taking a look. This repository is the reasoning core of CARETRACE —
the deterministic engine, its data model, the schema, and the Python reference.
The UI and the integrations live in a separate private repository.

Before anything else, please read the [disclaimer](DISCLAIMER.md). This is an
unvalidated prototype and is not for clinical use.

A few ground rules:

- Never put real patient data anywhere — not in issues, pull requests, tests, or
  fixtures. Use clearly made-up data.
- If you've found a security problem, don't open a public issue. See
  [SECURITY.md](SECURITY.md).
- Be decent to each other. The [code of conduct](CODE_OF_CONDUCT.md) applies.

## How to make a change

1. If it's more than a small fix, open an issue first so we can agree on the
   approach.
2. Fork, branch off `main`, and keep the change focused on one thing.
3. Add or update a test where it makes sense (`npm test`).
4. Make sure `npm run typecheck` passes.
5. Open a pull request that says what changed and why.

## Sign-off

Sign your commits off with the Developer Certificate of Origin — it's a one-line
statement that you have the right to submit the change:

```bash
git commit -s -m "your message"
```

Contributions to this repository are under its [AGPL-3.0](LICENSE) license.

Access to the private full-system repository is a separate thing and needs a
signed NDA (and a contributor agreement if you'll be sending code there); see
[LEGAL_NDA_CLA.md](LEGAL_NDA_CLA.md). The sign-off above covers this public
repository.

— Koushik Das
