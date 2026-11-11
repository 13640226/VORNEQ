# CAP_ACTOR_02 — Hobby Plan, S10 Log-Coverage Gap and Limited Documentary Acceptance (2026-11-11)

**Document ID:** `CAP_ACTOR_02_HOBBY_S10_DOCUMENTARY_RECORD_20261111`  
**Repository:** `13640226/VORNEQ`  
**Pinned source baseline:** `9f0c450827f918d7d93104f49499838808ee93d1`  
**Status:** `DOCUMENTARY_RECORD / LIMITED_OWNER_ACCEPTANCE / S10_EDGE_PROXY_OPEN`  
**Scope:** Staging evidence and local isolated verification; **no** production release, independently certified security closure, privileged CI or live diagnostic reactivation.

## 1. Provenance and decision references

This file is a **readable repository copy of previously recorded evidence and decisions**. It introduces no new tests, operator actions or security authorizations.

- [Staging positive run and shutdown record — Issue #448 comment 6781016656](https://github.com/13640226/VORNEQ/issues/448#issuecomment-6781016656).
- [Local negative/Redis follow-up plan — Issue #448 comment 6790585049](https://github.com/13640226/VORNEQ/issues/448#issuecomment-6790585049).
- [Owner-directed limited documentary acceptance — Issue #448 comment 6791935306](https://github.com/13640226/VORNEQ/issues/448#issuecomment-6791935306).
- [S10 Edge/Proxy read-access determination — Issue #448 comment 6792892680](https://github.com/13640226/VORNEQ/issues/448#issuecomment-6792892680).
- [Render log-provider follow-up — Issue #448 comment 6793375189](https://github.com/13640226/VORNEQ/issues/448#issuecomment-6793375189).
- [Hobby plan evidence and entitlement conclusion — Issue #448 comment 6793569552](https://github.com/13640226/VORNEQ/issues/448#issuecomment-6793569552).
- [Owner prospective independent-review policy — Issue #340 comment 6738990574](https://github.com/13640226/VORNEQ/issues/340#issuecomment-6738990574).

**Source caveat:** the current Render Billing → Plan screenshot supplied by the owner on 2026-11-11 visibly showed **Current Plan: Hobby** for the VORNEQ workspace. This screenshot was reviewed in the conversation but was **not** placed in this public repository, to avoid exposing unrelated Billing UI information. The screenshot **does not establish the historical plan on 2026-11-10**.

## 2. Accepted bounded technical evidence

| Verification | Bounded result | Evidence provenance |
| --- | --- | --- |
| Full Django regression, disposable PostgreSQL 16 | 1,040 tests, OK | Owner laptop's isolated Docker run on pinned source; log SHA-256 `46EBA121EF187D4BCE385991F1F17DC0400A7EE380B32396A60F2D869421EBD5` |
| Targeted actor-binding and diagnostic tests, disposable SQLite | 56 tests, OK | Isolated Docker test run; log SHA-256 `4076868AC9268B35D5F9FF8D004C530FE6AC773D0F506698E7D547128AF75479` |
| Redis 7 shared counter across separate processes | 10 allowed; 11th limited | Real disposable Redis, offline/isolated clients; log SHA-256 `47155517FC2CBA3CCCFE7ABBFA8E340AEF1DA9E87637F5C4D7ED640DBC84B888` |
| Redis unavailable | HTTP 503, fail closed | Disposable Redis stop and Django client; log SHA-256 `46EFE9C66670872B7D4896562DDC91A6EEE58EF73B8E363DFF0B45B2F31FD659` |
| S03–S06 / S08–S10-focused Django HTTP tests with real Redis | 6 tests, OK; S08 responses: HTTP 200 × 10, 429 × 1; local response/app logger privacy assertions passed | Local disposable DB + Redis, not Render Staging; log SHA-256 `5587C6AD762122A6C47C511DF68C485CB422867FD82C1E3DF156A9F6001E547C` |

These are **local test execution observations**, not full S01–S11 live Staging evidence. Raw logs remain in the owner-controlled isolated laptop workspace and are **not uploaded** by this commit. Hashes are integrity references, not a claim that third parties reproduced the tests.

## 3. Staging S10 evidence and limitations

**Examined Staging window:** `2026-11-10T21:45:00Z`–`2026-11-10T22:28:00Z`, Render web service `srv-dbm7dvc9v7es7393g70g` at the pinned SHA.

- A read-only paginated examination reviewed **2,044 `app` log records**. Render `app` logs included Django structured request entries and Gunicorn HTTP access lines.
- For the diagnostic URL, Django and Gunicorn both showed **six requests**: HTTP `200 × 1`, `403 × 3`, `404 × 2`. The isolated diagnostic app logger showed `pass × 1` and `deny (binding) × 3`.
- A bounded **pattern scan** of the examined app records did not find the specified plaintext secrets, cookies, bearer tokens, internal Redis/PostgreSQL URLs, known synthetic diagnostic account identifiers or non-correlation UUIDs. This **does not** guarantee absence of encoded/unknown secrets or leaks in other layers.
- The Gunicorn access line can include a query string; one observed diagnostic request carried a non-sensitive `utm_source` query key. A possible future privacy hardening is redaction of sensitive query parameters, if separately authorized and tested.
- The provider's `type=request` filter returned zero entries; the only log types surfaced for this window were `app` and `build`. **No separate native Render request-log, Edge, Proxy or CDN archive was independently examined**.

**Workspace plan:** owner-supplied Billing screenshot displayed **Hobby** on 2026-11-11. Render's [logging](https://render.com/docs/logging) and [plan feature](https://render.com/docs/platform-features-by-plan) documentation describes native HTTP request logs as a Pro+ workspace capability. Absence of a separate native request-log class in the checked Hobby workspace **fits the plan limitation**, but cannot prove what Render retained in its internal systems or whether historical request data exists.

**Provider support disposition:** no routine Render Support inquiry is required merely to explain the absence of a Pro-tier feature on the observed Hobby plan. A targeted read-only support inquiry is **optional** only if historical entitlement, retained provider edge events or an actual security closure decision requires such evidence. **No support ticket was sent.**

## 4. Explicit acceptance matrix and open issues

| Control | Documentary outcome |
| --- | --- |
| S01, S02, S11 historical live Staging | Prior evidence retained with its own attribution and caveats |
| S03–S06 | Local PASS only; not repeated live in Staging |
| S07 | Production OUT_OF_SCOPE |
| S08 | Real Redis + Django local HTTP PASS; not repeated live in Staging |
| S09 | Local privacy assertions PASS; live Staging coverage partial |
| S10 Django/Gunicorn | `ACCEPTED_WITHIN_SCOPED_APP_LOG_AUDIT` |
| S10 independent Edge/Proxy/provider logs | `OPEN / PROVIDER_NATIVE_EVIDENCE_UNAVAILABLE_IN_CHECKED_ACCESS` |
| S10 full security closure | `PARTIAL / NOT_PASS` |
| Independent review | `NOT_ESTABLISHED`; no owner-controlled account is treated as independent |
| C02, SC_07, GOV_BREACH_01, HARD_STOP/STOP_340 | Historical/security-governance findings **not closed by this file** |

The owner's prospective general policy allows owner-directed documentary review **within valid authority**, not a fabricated independent sign-off, broad security certification or repeal of any binding specific obligation.

## 5. No execution or release authorization

This is a **documentation-only** change. It does not modify application logic, settings, tests, workflow YAML, database state, Render billing or environment variables. The existing Staging diagnostic must **remain disabled**. This record does not permit account reactivation, staging enablement, migrations, CI with production secrets, Merge or Deploy.

A draft PR may run the ordinary **read-only, disposable-fixture** CI and security/quality checks. CI success, if achieved, verifies the submitted repository state **only within each workflow's scope**; it does not prove historical Edge/Proxy log coverage, grant merge authorization or produce a production GO decision.

```text
OWNER_DOCUMENTARY_ACCEPTANCE=LIMITED
WORKSPACE_CURRENT_PLAN=HOBBY__OWNER_SCREENSHOT_2026_11_11
HISTORICAL_WORKSPACE_PLAN=NOT_PROVEN
S10_APP_AND_GUNICORN=ACCEPTED_WITHIN_SCOPE
S10_EDGE_PROXY=OPEN_UNVERIFIED
S10_FULL=PARTIAL
NEW_LIVE_STAGING_TESTS=NONE
STAGING_DIAGNOSTIC=KEEP_DISABLED
INDEPENDENT_SECURITY_VERIFICATION=NOT_ESTABLISHED
PRODUCTION_RELEASE_GO=NO
FINAL=DOCUMENTARY_RECORD_ONLY__EDGE_PROXY_GAP_RETAINED
```

**Evidence ≠ authority. Owner documentary acceptance ≠ independent security certification.**
