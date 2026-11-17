# Citation source-ID instruction hardening V1

Date: 2026-11-17
Scope: prompt-contract hardening and offline regression tests only.
Baseline: `31bf2c08f70c713665700a490161869d63fb1768`

## Incident

During an authorized Staging conversation (question about solar cells), the chat
displayed an error indicating that a generated citation used an unknown or
invalid source identifier. A Render log entry at 20:42:53 UTC reported
`ai_evidence_rejected reason_code=citation_identity_rejected`.

That signal proves the local fail-closed validation rejected the output; it
does **not** identify the exact raw identifier the model produced. Do not log
the model's raw response, full prompts, private history, keys or quotes merely
to reproduce this issue.

## Remediation

The fixed system instructions now tell the model to:
- Cite only one or two distinct entries from the **current request** `sources`
  array; copy each `source_id` exactly, including case.
- Never cite `source_key`, URL, title, list index or historical conversation
  content as `source_id`.
- Copy `evidence_digest` from the same chosen source and quote an exact,
  bounded substring of that source's excerpt.
- Omit unsupported assertions rather than invent IDs, digests or quotes.

The trusted IDs remain assigned by `authorized_web_context`. The provider's
input payload, strict Structured Outputs schema, and deterministic validator
are unchanged. Validity is checked locally after provider execution.

**No second provider attempt** is made when citation validation fails. A
rejected model response may still incur a billable provider charge. The
existing Ledger settlement and persistent request guard must be preserved.

## Security properties (unchanged)

- `CitationIdentityRejected` on unknown, case-changed, foreign-key, duplicate,
  missing or oversized citations.
- `CitationDigestRejected` when a trusted source's digest does not match.
- `CitationQuoteRejected` when quote does not occur verbatim in the same
  source excerpt.
- `GeneratedAnswerRejected` for invalid schema or a forged claim of
  independent verification.
- `verified=False` remains mandatory. Exact quotes and matching IDs do not
  prove semantic truth or independently verify claims.
- No automatic correction of fabricated citations, no extra OpenAI retries,
  no changes to the model API, database, cost accounting or migrations.

## Verification

`apps/ai_core/tests/test_ai_citation_source_id_contract_v1.py`:
14 synthetic offline tests with no external OpenAI calls or network access.
The suite asserts valid and forged citation behavior and that an invalid model
identifier is rejected after exactly one mocked generation attempt.

The new instructions reduce the chance of citation-identity mistakes but do
not guarantee the model will comply. The next Staging provider trial requires
separate owner approval, a fresh SHA-bound preflight and Ledger verification.

No merge, deploy or production changes are in this patch.
