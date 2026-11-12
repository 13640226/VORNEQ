# VORNEQ AI Development Backend — Live OpenAI E2E Harness (V1)

**Repository:** `13640226/VORNEQ`
**Base:** `822081ffa2585af479143a307048a6e90f78898f` (merged Phase C PR #587).
**Branch:** `feat/ai-development-live-provider-e2e-20261112`
**Authority:** Development implementation and local-only tests; **NO MERGE / NO DEPLOY / NO PROD CONFIGURATION CHANGE** by this task.

## Existing integration
The Django endpoint `POST /api/ai/v1/ask-grounded/` is implemented by `apps/ai_core/views_phase_b.py`, which instantiates `OpenAIResponsesProvider` and calls the real OpenAI Responses `responses.parse` SDK route. Auth, CSRF, input size, evidence validation, disabled-by-default guard and request budget remain on the server. The Phase C chat page `GET /api/ai/v1/chat/` calls the same endpoint. Both are **development only**.

OpenAI direct SDK was previously checked through one user-run manual smoke call, reported `completed` on model `gpt-6-luna` and 20 input / 16 output tokens. That is **NOT** proof of a live authenticated VORNEQ endpoint call.

## New harness
- `apps/ai_core/tests/test_ai_backend_e2e_mock.py`: 3 automatic tests using Django test database + CSRF client. Includes one full endpoint request through the REAL OpenAI SDK parse path using an `httpx2.MockTransport` and synthetic public Citation; negative missing-CSRF and no-source tests. No Internet egress.
- `apps/ai_core/tests/manual_ai_backend_live.py`: separately named manual test (outside `test*.py` discovery) for **exactly one** real OpenAI request through the complete Django authenticated Phase B endpoint. Guarded by explicit environment/authorization settings. Uses a synthetic public Citation in place of real retrieval and an ephemeral Django test user in an isolated SQLite test DB. It never sends private/tenant records. It validates `HTTP 200`, `verified=false`, a grounded_draft response, one citation, expected synthetic source key and URL. Prints safe result metadata but not the model answer, secret, prompt or raw SDK error.
- `scripts/ai_dev_compile_catalogs.py`: compiles .po to local .mo with the preinstalled Babel API to match CI preprocessing.
- `scripts/ai_dev_live_backend_e2e.ps1`: local PowerShell runner with default **offline** mode and explicit `-Live`. Checks for external `DATABASE_URL`/`REDIS_URL`, sets development-only flags, verifies SQLite, runs local `collectstatic` and Django check. For live mode, requires user typing `YES`, then reads key via secure hidden local prompt into process memory; cleans the process environment after execution.

## Run on authorized Windows laptop

Offline (no API key or Internet egress):

```powershell
& "$env:USERPROFILE\Downloads\VORNEQ-AI-Dev-Integration-20261112\scripts\ai_dev_live_backend_e2e.ps1"
```

Single **billable** live provider call via the REAL authenticated Django endpoint:

```powershell
& "$env:USERPROFILE\Downloads\VORNEQ-AI-Dev-Integration-20261112\scripts\ai_dev_live_backend_e2e.ps1" -Live
```

Before running `-Live`, confirm the OpenAI project billing budget and access to model `gpt-6-luna`. A user must physically approve one billable request by typing `YES`, then paste a project-scoped key at the hidden prompt. This is explicitly **not a request to send the key in a chat, screenshot, GitHub or log**.

Results of live test must include `REAL_VORNEQ_BACKEND_E2E=PASS`, and `VORNEQ_BACKEND_HTTP=200`. If failed, do not report a real connection success. A failed provider call can still incur a small cost.

## Limitations
- Live E2E source is **synthetic and patched**. This verifies request-to-provider-to-validation wiring only; **real public search, published visibility and tenant isolation are not verified** by this test.
- OpenAI SDK and its transient dependency set are installed in an isolated local virtual environment; the production/CI dependency lock is unchanged and some SDK tests skip on official CI. Independently review and hash-lock dependencies before operational rollout.
- Citation hash/quote integrity does not prove semantic entailment. All generated drafts remain `verified=false`.
- Existing request limit is **not** a monetary billing limit and not a production-grade distributed atomic quota.
- No persistent chat, no model-controlled tools, no automated logging of prompts, no database migrations, no Render/Production changes or deploy actions.
- Existing G4/STOP_340/HARD_STOP/C02/SC_07/GOV_BREACH_01 risk status and independent security review evidence are unaffected.

## Evidence
Offline Django SDK mock E2E: 3/3 PASS in development SQLite after local gettext and static preprocessing. Full AI Core and Homepage test suite should be recorded separately on this branch. Real backend result is **PENDING until the owner executes `-Live` locally**.

```text
PHASE_C_REAL_OPENAI_SDK_DIRECT_SMOKE=USER_REPORTED_PASS
BACKEND_OFFLINE_REAL_SDK_E2E=PASS
BACKEND_LIVE_PROVIDER_E2E=PENDING_OWNER_LOCAL_KEY
PRODUCTION_AI=DISABLED
MERGE=NOT_AUTHORIZED_BY_THIS_TASK
DEPLOY=NOT_AUTHORIZED
```
