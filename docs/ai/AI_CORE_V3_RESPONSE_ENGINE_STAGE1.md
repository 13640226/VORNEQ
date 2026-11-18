# AI Core V3 — Stage 1: bounded response engine

This branch is an **isolated first step**, not a general AI parity or
long-term memory implementation.

## Delivered

- Code-defined fixed response guidance for Persian, German and English.
- Simple deterministic hints to answer each part of a multi-part question,
  only when supported by the current trusted excerpts.
- Default 1000-character validated answer bound preserved; optional 2400
  characters in **development and staging only**.
- Feature is OFF by default: `VORNEQ_AI_RESPONSE_V3_ENABLED=false`.
  Production cannot activate this pilot even if the setting is true.
- Shared prepaid Ledger now measures the full effective instruction text
  sent to the provider, including existing Persian writing guidance, before
  reserving the request. No extra provider call or retry is introduced.
- Existing owner-bound PostgreSQL conversation history remains unchanged;
  optional longer completed assistant turns respect existing context turn and
  character budgets.

## Not changed

- Source retrieval, numeric-claim rejection, citation identities, digests and
  verbatim quote validation; `verified=false` is still compulsory.
- Runtime kill switch, recovery/TOCTOU gate, cost ceilings, model selection,
  Production authorized SHA, allowlist, migrations or database structures.
- File/image/voice input, streaming, multi-source retrieval, consent-based
  long-term memory, private document retrieval and autonomous tools are
  deferred to separate design/security reviews.

## Test and release policy

Run CI with Python 3.11 and 3.12 on SQLite and PostgreSQL, plus Security
Audit and global quality workflows. Tests use synthetic data and mocks: no
paid OpenAI requests, no Production DB writes.

**No Production deploy is authorized by this branch or its CI.** Staging
activation requires a separate SHA-scoped decision, then a bounded pilot with
usage and Ledger checks. Do not interpret improved text quality as independent
factual verification.
