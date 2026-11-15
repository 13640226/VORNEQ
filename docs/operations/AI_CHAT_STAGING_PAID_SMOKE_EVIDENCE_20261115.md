# VORNEQ AI Chat — Paid Staging Smoke Evidence (2026-11-15)

**Scope:** Documented evidence from an owner-authorized, Staging-only paid OpenAI smoke test. This document does not authorize a new paid call, a Production deployment, or any migration.

## Runtime baseline

| Item | Observed value |
| --- | --- |
| Repository | `13640226/VORNEQ` |
| Staging service | `vorneq-staging` (`srv-dbm7dvc9v7es7393g70g`) |
| Staging commit | `d9c92131a235d32b7dd62fd729f19aed0cad3b82` |
| Staging deploy | `dep-dbsml40n74is73aavi4g` — LIVE |
| Production commit | `3236441923eb1a1ea5f78b83d747532c5bb8da99` — unchanged |
| Staging database | `vorneq_staging_db_9i8v` |
| Recovery | Enabled on Staging; durable migration `ai_core.0002_aichatrequestguard` applied earlier |
| Provider | OpenAI Responses API, model `gpt-5-mini` |
| Authorization | Active allowed Staging superuser; real Django authentication, session and CSRF |

The Staging `VORNEQ_AI_STAGING_AUTHORIZED_SHA` pin was updated to the exact deployed SHA. Prior to the pin correction, the live chat was fail-closed. After the correction, unauthenticated `GET /api/ai/v1/chat/` returned HTTP 401 instead of HTTP 404. No Production setting was modified.

## One-time paid smoke observations

Both attempts used distinct request UUIDs, the same non-sensitive public question ("What is quantum computing?"), real retrieval, the live OpenAI provider, and the shared prepaid ledger. The output-token limit was overridden **only inside each test process**; no source-code output limit or permanent setting was changed.

| Attempt | Output cap | Provider HTTP | VORNEQ HTTP | Input tokens | Output tokens | Internal observed cost (micro-USD) | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 512 | 200 | 503 | 674 | 512 | 1,193 | `incomplete`, reason `max_output_tokens` |
| 2 | 2,048 | 200 | 200 | 674 | 1,299 | 2,767 | Completed |

The first request demonstrated that HTTP 200 from OpenAI does **not** imply a complete structured response. VORNEQ rejected it as `provider_unavailable` and stored the failed outcome for the UUID; same-UUID replay made no second provider call.

The second request returned an answer with two citation entries (Wikipedia "Quantum computing" and "Superconducting quantum computing"). The response reported `model_status=generated`, `grounded_status=citation_and_quote_checked_claims_unverified`, and `verified=false`. A recovery-status GET returned `200 / completed`. Repeating the identical POST with the same UUID returned the cached 200 response without another provider invocation or cost reservation.

## Cost ledger verification

A subsequent **read-only** query of the actual Staging-linked ledger verified exactly two new `BudgetReservation` records for these attempts, both `finalized`. The first recorded `ProviderInvalidResponse`; the second recorded `completed`.

- Total internally observed cost: **3,960 micro-USD = $0.003960 USD**.
- Internal remaining allowance after both: **8,971,102 micro-USD = $8.971102 USD**.
- Both cost amounts are *application-side estimates based on observed provider token counts*, **not an OpenAI invoice or a real-time provider account-balance attestation**.

## Other test evidence and boundaries

- Actual Staging PostgreSQL + Redis durable-recovery service integration: **16/16 PASS**, with no OpenAI calls.
- In-process Django HTTP / authentication / CSRF with mocked model: **22/22 PASS**; temporary test users and guard rows rolled back, test cache keys deleted.
- Real paid Django HTTP request, grounded response, recovery and same-UUID deduplication: **PASS on attempt 2**.
- Post-test Staging service LIVE; `/health/` database/cache/storage checks OK. Production remained on its previous SHA.
- These tests used the authenticated Django HTTP client **inside the Staging runtime**, not a separate external desktop or mobile browser session. Browser display, interactive UI and mobile acceptance remain open.
- App-side SHA, actor and budget guards still apply. Redis loss does not erase PostgreSQL's durable guard, but restoring an old database backup could undo durable request history; globally exactly-once provider billing cannot be claimed.
- **Global C02 remains `OPEN_CRITICAL`; Production AI enablement is not approved.**

## Source of evidence

- GitHub Issue #407, owner authorization and paid smoke record: https://github.com/13640226/VORNEQ/issues/407#issuecomment-6891690810
- First scoped test source SHA-256: `B87FBF20E7FCE01E4B7ADB754FB59BA0EBA39BB368A020CA413E82E4A5EC5954`
- Second scoped test source SHA-256: `F27DA364C835CF8660AEF2CE0861BA966275AAAC190ED6B54059480DDDD79834`
- The source test scripts were executed once per new UUID and deliberately **not committed**, to avoid an accidental repeated paid run.

**Decision:** Staging paid provider + recovery + internal ledger verification PASS. External browser/mobile acceptance pending. Production unchanged; global C02 remains open.
