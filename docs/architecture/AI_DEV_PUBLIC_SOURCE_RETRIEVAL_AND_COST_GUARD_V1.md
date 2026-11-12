# VORNEQ — Public Retrieval and Cost Guard Verification V1

**Repository:** `13640226/VORNEQ`
**Scope:** Development-only enhancement to Draft PR #588, based on `822081ffa2585af479143a307048a6e90f78898f`.
**Authority:** local implementation and test; NO MERGE / NO DEPLOY / NO LIVE BILLABLE CALL in this verification run.

## 1. Real search adapters, isolated data

New test module `apps/ai_core/tests/test_ai_public_retrieval_cost_guard.py` creates synthetic, clearly non-secret data within Django's disposable SQLite TEST database. Crucially, it **does not mock `retrieve_public` or `UnifiedSearch`** for the positive path: real ORM SQL queries run through the production source adapter classes, with result serialization, citation creation, digest/quote validation and the authenticated Django endpoint.

The fixtures include:
- A published Article and an unpublished Article containing the same exact search marker.
- A published LibraryItem and an unpublished LibraryItem with that marker.
- A published AudioItem with an audio file.
- A held MediaAsset containing the same marker, intentionally outside AI's allowed public adapters.

Assertions: precisely three public sources returned (Article, LibraryItem, AudioItem); unpublished sources excluded; held media excluded; an authenticated endpoint receives grounded, still-unverified draft output; missing public evidence abstains with NO provider call.

**Limitation:** These are REAL adapter/ORM operations over synthetic fixtures, NOT real customer content or an inspection of Production database rows. Separate strictly read-only public HTTP GET requests to both staging and production `/en/search/?q=VORNEQ` returned HTTP 200 and text/html on 2026-11-12. That confirms public endpoint reachability only; it does not independently verify returned source truth, publication state or tenant isolation for live records.

## 2. Development-only API request cost guard

The existing `apps/ai_core/engine/budget.py` keeps user limits at 6 requests/minute and 30 requests/day, with the additional conservative `global_per_day=10` guard across all development users on a **shared** Django cache. All three counters are reserved **before** constructing an OpenAI provider or sending any model request; a failed/over-limit counter fails closed and returns the existing 429 rate_limited response. A negative test verifies a second endpoint request after exhausting the global limit returns 429 without provider invocation.

This is a request COUNT guard, not a hard monetary cap: it is not durable or distributed with in-process LocMemCache; process restarts and separate workers may bypass aggregate counting. A distributed backend such as Redis is required to share the counter across workers, but this development test does not connect to or reconfigure any Redis instance. Actual provider output stays capped at 512 tokens per request, retries=0, timeout=15s, `tools=[]` and `store=False` as previously implemented.

## 3. OpenAI billing hard limit (separate dependency)

The OpenAI platform project's **Enforce a hard limit** control must be set by an authorized project owner before further real API calls. A spend alert does not stop requests, and even enforced billing limits may have delayed enforcement. This session **did not inspect or change** that account setting and cannot claim a verified dollar cap.

The manual `scripts/ai_dev_live_backend_e2e.ps1 -Live` now explicitly requires the owner to confirm `LIMIT_CONFIRMED` before `YES` and secure hidden key entry. These answers are owner attestations, not API-verified billing settings. Dry/offline tests need no key and make no paid API calls.

Official reference: https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform

## 4. Validation evidence and acceptance boundaries

- Local Django focused AI Core and Homepage tests: **73/73 PASS**, SQLite synthetic ephemeral TEST database, no provider egress (2026-11-12).
- New public-adapter/guard tests: **7/7 PASS**, including 429 before provider invocation.
- Direct owner-run live OpenAI backend test previously reported PASS in PR #588, using a SYNTHETIC public source. This follow-up DID NOT re-run a paid call.
- Staging and production public search GET: **HTTP 200**, read-only request. No real provider API interaction or deployment occurred.
- The global request ceiling works locally but monetary spending and reliable cross-process enforcement remain **UNVERIFIED**.
- No private, tenant-specific or actual production database data was processed by the tests.
- Source citation identity and verbatim evidence quotes are verified structurally; generated model claims remain `verified=false`.

## 5. Decision boundary

Recommendation for this PR: `CODE_MERGE_CANDIDATE_AFTER_SHA_BOUND_CI_AND_OWNER_AUTHORIZATION` because the scope is a development-only safer test harness and request-count guard. Do NOT infer production deployment or production AI activation readiness. `HARD_STOP`, `STOP_340`, `C02`, `SC_07`, `GOV_BREACH_01` and G4 owner-only deployment policy remain unchanged.

```text
REAL_PUBLIC_ADAPTER_SQL_TEST=PASS_ON_SYNTHETIC_SQLITE_FIXTURES
LIVE_PUBLIC_SEARCH_ENDPOINT=HTTP_200_ONLY
DEV_GLOBAL_REQUEST_GUARD=LOCAL_429_PASS
OPENAI_PROJECT_HARD_SPEND_LIMIT=NOT_VERIFIED
LIVE_PROVIDER_E2E=PREVIOUS_OWNER_EVIDENCE_PASS
REPEAT_LIVE_PROVIDER_CALL=NOT_EXECUTED
PRODUCTION_AI=DISABLED
MERGE=NOT_AUTHORIZED_BY_THIS_REPORT
DEPLOY=NOT_AUTHORIZED
```
