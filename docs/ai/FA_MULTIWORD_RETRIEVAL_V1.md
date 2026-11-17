# Persian multiword-name retrieval V1

Date: 2026-11-17

## Observed failure and scope

The Staging chat returned `INSUFFICIENT_EVIDENCE` for the Persian question
`ابن‌سینا که بود؟`. This is not proof that the upstream Wikipedia API
failed: the original runtime search response was not captured.

A reproducible source-code gap was found: ranking originally tokenized the
ZWNJ spelling `ابن‌سینا` as `ابنسینا`, but the article title
`ابن سینا` became two tokens. The overlap score could therefore be zero,
discarding a relevant retrieved article before any model call.

## Bounded remediation

1. **Rank-only normalization** (Persian): index both sides of a ZWNJ and
   adjacent two-part joins of source titles and excerpts. Recognize
   `ابن‌سینا`, `ابن سینا` and `ابنسینا` without changing the actual
   source text, source URL, evidence digest, citations or response language.
   Source title and excerpt are processed separately to avoid cross-field
   phrase joins. Other languages keep their existing ranking behavior.
2. **One fallback query**: only if the first ranked/authorized evidence list
   is empty, only when the Persian query contains a ZWNJ between word
   characters, replace that ZWNJ with a space and retry via the *same*
   configured source provider. No aliases or facts are invented.
3. **Fail-closed**: no retry after a retrieval transport error; no retry
   for a supported source on the first pass; at most two retrieval rounds.
   Both rounds retain host allowlists, safe input screening, DNS/IP checks,
   response limits, ranking and citation validation. If both fail,
   `INSUFFICIENT_EVIDENCE` is returned without generating an answer.

The Wikimedia retriever still makes one HTTP call **per** search invocation.
The Global AI orchestrator may invoke it a second time for the narrowly
bounded fallback. This adds up to one extra retrieval round, **not** an
OpenAI/model retry. All paid model, Ledger and idempotency safeguards remain.

## Verification and explicit limits

- Synthetic-only tests in
  `apps/ai_core/tests/test_fa_multiword_retrieval_v1.py` test cross-spelling
  relevance, fallback behavior, request bounds, untrusted domains, no provider
  on no evidence, and the actual Wikipedia search request parsing interface
  through a fake transport.
- Existing 40 measured Persian keyword queries remain byte-identical
  (no change to `search_keywords`).
- No external Wikipedia connectivity is required for tests; no OpenAI SDK
  request is made.
- The fix is **not** a general semantic search system and does not guarantee
  that Wikipedia has relevant evidence for every spelling/name. Search
  provider availability and factual citation correctness require separate
  Staging validation.
- GitHub merge and Render deploy are separate, not authorized by this patch.
