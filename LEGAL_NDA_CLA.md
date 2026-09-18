# Access, confidentiality, and contribution terms

This document explains how CARETRACE is licensed, how to get access to the parts
that are not public, and the two legal agreements involved. It is written for two
readers: anyone who wants to work with the full system, and me, as a checklist
for briefing a lawyer.

> This is not legal advice, and the summaries below are not the agreements
> themselves. CARETRACE is health-adjacent software, so before any of these
> documents is used it should be drafted or reviewed and finalised by a qualified
> attorney in the relevant jurisdiction.

## How the project is split

CARETRACE is released as **open core**. The reasoning engine — the deterministic
evidence logic, its data model, the schema, and the Python reference — is public
and licensed under AGPL-3.0. Everyone can read it, run it, test it, and build on
it under that license.

The rest of the system — the user interface, the storage and integration layers,
the OCR/layout service, hospital multi-tenancy, and the FHIR/HL7 work — is not
open. It is made available for evaluation and contribution to people who have
signed the agreements described below.

## Why there are two agreements, not one

The goal is to be able to share the full source with someone once they have
signed an agreement. That actually needs two separate agreements, because they do
two different jobs.

**A Non-Disclosure Agreement (NDA)** governs what someone may do with what they
see. It is what allows me to give a person access to the private code while
keeping that code confidential — they may study and test it, but they may not
disclose, redistribute, or reuse it outside the agreed purpose. Signing the NDA
is what unlocks access to the private repository.

**A Contributor License Agreement (CLA)** governs what happens to code that
someone sends *back*. By default, a contributor keeps copyright over their
contribution, which would later prevent me from relicensing the private system or
offering it commercially. A CLA resolves this in advance by having the
contributor license (or assign) their contributions to the project. Anyone who
only wants to evaluate the system needs the NDA; only those who will submit code
to the private repository also need the CLA.

The public core works differently and needs neither of these. Contributions to
it are made under a lightweight Developer Certificate of Origin sign-off, as
described in [CONTRIBUTING.md](CONTRIBUTING.md).

## What the NDA should cover

- **The parties** — me (or my company), and the person or organisation receiving
  access.
- **What is confidential** — the private repository and everything in it,
  including code, documentation, and any credentials.
- **Permitted use** — evaluation, testing, and (where applicable) contribution
  only; no redistribution, no derivative products, and no reverse engineering
  beyond what any applicable license allows.
- **What is excluded** — information that is already public (the open core), or
  that the recipient developed independently.
- **How long it lasts** — the term of the agreement and how long the
  confidentiality obligation survives after it ends.
- **Return or destruction** — the recipient's obligation to return or destroy the
  confidential material when access ends.
- **No license granted** — the NDA grants access for the stated purpose only, not
  ownership, and not a license to use the software in production.
- **Governing law and jurisdiction.**

## What the CLA should cover

- A broad license (or an assignment) from the contributor to the project for
  their contributions.
- A warranty that the contributor has the right to contribute the work and that
  it does not infringe anyone else's rights.
- A patent grant from the contributor covering their contribution.
- Clear scope: it applies to contributions made to the private repository.

Rather than drafting one from scratch, it is worth showing a lawyer an
established template — the Apache Individual and Corporate CLAs, or the Harmony
Agreements — as a starting point. On GitHub, a tool such as CLA Assistant can
collect and record signatures automatically.

## How to get access to the full system

1. Request access, describing who you are and what you want to evaluate.
2. Sign the NDA — and the CLA as well, if you intend to submit code.
3. I verify the signed agreement and keep a copy on record.
4. I add your GitHub account to the private repository with the least access the
   work requires.
5. Access is revoked when the engagement ends.

If you work with a hospital or a public-health body that would like to trial
CARETRACE in a non-production setting, please say so when you get in touch.

## A note on deployment

Making CARETRACE freely available to public and government hospitals is a
separate effort from open-sourcing it, and a longer one. Using software in real
patient care generally requires clinical validation and, depending on the region
and how the software is classified, regulatory clearance. Until that work is
done, CARETRACE should only be offered for evaluation and shadow-mode pilots —
run alongside an existing, validated process, never in place of one — with the
[disclaimer](DISCLAIMER.md) made clear to everyone involved. The warranty
disclaimer in the license is necessary, but it is not a substitute for that
process.

— Koushik Das
