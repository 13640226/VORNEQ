# VORNEQ AI Core Phase B — Isolated Grounded LLM MVP V1

**Base:** `39ac14ef38e370898b3923add9990f7cd715bdf8` (verified against remote main)
**Branch:** `feat/ai-core-phase-b-grounded-llm`
**Authority:** bounded owner authorization for isolated development, tests, commit/push and Draft PR ONLY.
**Production/Staging activation:** NOT AUTHORIZED. **Merge/Deploy:** NO.

## Implementation

- Keeps existing `apps/ai_core/gateway.py` and `POST /api/ai/v1/ask/` fully offline.
- Adds opt-in `POST /api/ai/v1/ask-grounded/` behind **both** `VORNEQ_ENV=development` and `VORNEQ_AI_PHASE_B_ENABLED=true`; always HTTP 404 in staging/production.
- Existing session authentication, CSRF protection, request body cap 2048 bytes, fa/en/de input; unknown/duplicate fields denied.
- A separate `providers/openai_responses.py` adapter calls Responses `parse` with a strict Pydantic schema, `tools=[]`, `store=False`, no retries, bounded output tokens, timeout and server-side credential. It has **no default model**, never calls external APIs in CI, and is loaded only in explicit development-only requests.
- New optional runtime libraries **openai** (which brings **pydantic**) are **not** added to `requirements.txt` or any existing hash-pinned CI lock. This is deliberate: a separate reviewed dependency-lock update is required before any real SDK execution. Current CI tests use mocks and cannot validate live API interoperability.
- Sources: public-only published Article/Product/Library/Audio search from Phase A, max three; source excerpts capped at 300 chars; deterministic SHA256 digest of *sanitized source snapshot* and verified source ID.
- Output validation rejects missing/unknown source IDs, digest mismatch, non-verbatim evidence quote, invalid shapes, claimed verified truth or unsafe payloads. Every accepted generated draft explicitly sets `verified=false` and `grounded_status=citation_and_quote_checked_claims_unverified`.
- No source means `INSUFFICIENT_EVIDENCE` with **no provider call**. Provider errors fail closed (503/504), with no silent fallback or secret contents.
- Known injection patterns, hidden format/control characters and PII are filtered/redacted before the provider boundary; untrusted context is sent only in a user-role data payload and never spliced into system instructions.
- Crude development-only cache-based per-user quota (6/min and 30/day), fail closed on cache failures. It is **not** audited financial accounting or distributed production rate enforcement.
- No model tools, agents, file uploads, private document retrieval, database migrations, conversation history or persisted prompt/response logs.

## Honest limitations / activation blockers

1. **CITATION_EXISTS != CLAIM_SUPPORTED**: Digest plus verbatim quote only verifies a source-snapshot relationship, **not semantic or factual support for generated claims**. Factual verification or NLI/claim-splitting must be separately implemented and evaluated before trusted claims.
2. Search adapters are public/published-only, but this phase does **not** implement new private-document or permission-aware tenant retrieval. Private/tenant sources are rejected by allowlisted source keys. Independent authorization audits of source schemas remain required.
3. Pattern matching is not a complete prompt-injection defense. Obfuscated/multilingual/adversarial payloads can evade it; comprehensive adversarial evaluation is pending.
4. Cache quotas are process/backend dependent and do not constitute trustworthy global spend limits. Implement shared atomic quotas and authoritative provider-usage accounting before staging/production activation.
5. Strict schema fields are parsed by Pydantic when the optional SDK is installed; actual Responses API compatibility and provider error classes were **not live-tested**. Pin dependencies with reviewed hashes, integration-test against a controlled test environment and keep API credentials out of CI.
6. Live UI is not integrated. The new API is development-only and returns 404 to real staging/production.
7. Existing G4, STOP_340, HARD_STOP, C02, SC_07 and GOV_BREACH_01 historical findings are unchanged. Proposal G4 external attestation remains unactivated.

## Local test recipe (SQLite only)

Use a clean isolated worktree at the stated SHA. NEVER reuse production DATABASE_URL or credentials.

```powershell
$env:VORNEQ_ENV='development'
$env:DJANGO_SECRET_KEY='synthetic-test-only'
$env:DJANGO_DEBUG='1'
$env:DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1,testserver'
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
python manage.py check
python manage.py test apps.ai_core.tests
```

No real API calls were made in this test plan. For official acceptance, check GitHub CI (SQLite/PostgreSQL), Security Audit, Global Quality and Backup Restore on the **exact** PR SHA.

## Final state after coding

```text
IMPLEMENTATION=ISOLATED_DRAFT
OFFLINE_PHASE_A=UNCHANGED
PHASE_B_PROVIDER=OPTIONAL_DEVELOPMENT_ONLY
PROVIDER_SDK_AND_REAL_CALLS=NOT_VALIDATED
CITATION_ALIGNMENT=DETERMINISTIC_QUOTE_ONLY
SEMANTIC_FACT_VERIFICATION=NOT_IMPLEMENTED
FINANCIAL_SPEND_ENFORCEMENT=NOT_IMPLEMENTED
PRODUCTION_AI=DISABLED
STAGING_AI=DISABLED
MERGE=NO
DEPLOY=NO
```
