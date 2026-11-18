# VORNEQ AI Core V3 — Stage 2 implementation (Draft / disabled)

Based on `main` SHA `3de4f9fa2b3a11fd13ba3fd476fa1265481cbbba` and the locally reviewed
`AI_CORE_V3_AUDIT_AND_STAGE2_CONTRACT_v2.md` (2026-11-18).

## Deployment policy

**No migration, Merge, Deploy, Render environment changes, or paid OpenAI calls
are authorized by this work.** Production remains permanently in the legacy
path; the new pilot is strictly opt-in for development or separately approved
staging. Owner must authorize every later merge/deploy/billed evaluation.

`VORNEQ_AI_RESPONSE_V3_STAGE2_ENABLED=false` by default, requiring
`VORNEQ_AI_RESPONSE_V3_ENABLED=true` and `VORNEQ_ENV` in
`development,staging`. These controls are rechecked in code and in tests.
No model-request retry; no new source hosts, tools, document access or memory.

## Delivered code paths

- Wikipedia staged retrieval 5 excerpts of up to 1,500 characters, behind
  Stage-2 flag, retaining the vetted HTTPS host and DNS/IP protections.
  Legacy defaults are still 3 and 500.
- Deterministic, exact-substring passage identifiers `S1.P1` etc, up to
  24 passages (80–300 chars), with original trusted evidence digests unchanged.
- Strict Pydantic `SectionedAnswerSchema` and local fail-closed validation:
  1–6 sections; answer sections require 1–4 valid refs; 8 unique passage refs
  overall; gaps cannot cite passages or introduce numbers; every number is
  assessed against *that section's* cited passages and original user question.
- Only the server builds citations; `verified=false` denotes that this is
  **not** independent semantic claim verification.
- Persian prose-only `ي/ك → ی/ک` and bounded ZWNJ normalization, with
  URLs, evidence, quote text, source titles, IDs, digests and numerals untouched.
- New `format_version=2` adds `sections` while preserving the flat `answer`
  and the **list** type of `citations`. Nested optional `passages` are
  allowlisted and bounded before storage. Legacy `classify()` behavior and
  the original `validate_generated` are preserved.
- The existing `AIMessage.content` stores the flat answer; `AIMessage.citations`
  remains a list. After a database reload, sections render as flat text with
  passage mappings rather than full separate section blocks. A separately
  reviewed and owner-approved additive `0004` migration would be needed
  before any claim of persistent section layouts in Production.
- Frontend reads a bounded server-rendered answer limit (1000/2400); the
  previous hard-coded 1000 JS bug is corrected. Five citations, passage
  references, and structured text-only sections are supported in the opt-in
  Stage-2 path, with `textContent` and responsive styles.
- Shared prepaid Ledger counts the **exact** effective SDK instructions and
  Stage-2 payload, and reserves worst-case 3072 model-output tokens only in
  approved staging pilot. No auto-retry or settlement relaxation.

## Evidence and limitations

- The parser and quote identity validators do **not** prove semantic factual
  truth. Conflating citation references with verified facts is prohibited.
- Additional evidence is still Wikipedia only; the new cap is not a
  multi-provider fact-checker.
- Larger outputs at 3072 tokens under the existing 60-second staging timeout
  may return `incomplete`, fail-closed, and still consume billed tokens.
  No 60s performance promise has been made.
- The benchmark fixture has 60 Persian, 20 German, 20 English *public synthetic*
  questions. `scripts/ai_eval_stage2.py` computes metrics solely from
  pre-recorded aggregate Staging values; it neither calls OpenAI nor validates
  claim truth. Actual AC13 baseline and live trial have **not** been run.
- Stage 2 does not increase question input beyond 200 chars and does not
  implement memory, file/vision input, model choice, streaming or tools.
- Python 3.14 image pinning is tracked in a **separate unmerged PR #652** and
  is not bundled in this branch.

## CI / acceptance

Offline test contracts cover flag isolation, exact passage identity, Unicode
and number handling, evidence-scoped claims, strict citation refs, Persian
prose isolation, legacy storage/replay compatibility, full Ledger prompt
reservation and the 100-question metric-only fixture. Full Django CI on
SQLite and PostgreSQL and all repository security workflows must be green.

AC11 requires a real-browser Playwright RTL/mobile/overflow verification in
Staging before merge authorization; static HTML/JS contract tests alone are
not equivalent to visual runtime verification. AC13 additionally requires
a separately approved bounded paid Staging run with an OpenAI project budget.

No Production activation is allowed with this Stage-2 flag.
