# VORNEQ AI Phase C — Real LLM Integration & Chat UI (development preview)

**Scope:** `feat/ai-core-phase-c-real-llm-chat-ui` (isolated from main at `3e7b1e1918b69cf76ca052ef4f0cebd906c82d66`).
**Authority:** User-directed branch development and Draft PR only. **Merge=NO / Deploy=NO / Production=UNCHANGED**.
**Feature default:** OFF in all environments. Even with the flags set, Phase B and Phase C cannot run in Staging/Production.

## Delivered

- Phase B `apps/ai_core/providers/openai_responses.py` is reused unchanged. Its Responses API `client.responses.parse(..., text_format=GroundedAnswerSchema, tools=[], store=False)` path was verified using **OpenAI Python SDK 3.49.0**, **Pydantic 2.14.3**, and **httpx2 2.16.0** with a local `httpx2.MockTransport`. This was a synthetic HTTP 200 response through the real SDK parsing code, **NOT a live API connection or factual model evaluation**.
- Adds `VORNEQ_AI_PHASE_C_ENABLED` as an independent development-only flag, dependent on Phase B. The server-guarded page `GET /api/ai/v1/chat/?lang=fa|de|en` returns 404 in production/staging and unless both development flags are enabled; anonymous users get 401.
- Homepage only reveals a development-preview chat link to authenticated users when both flags are active; otherwise Search UI, disabled AI label and public copy stay unchanged.
- Responsive RTL/LTR chat page with native form, CSRF token, `fetch` of existing `POST /api/ai/v1/ask-grounded/`, loading/error states, citation links, clear-chat action, small text-only messages and no HTML/Markdown injection (only `textContent`). Source URLs are restricted to validated relative same-origin paths.
- No browser API key, no third-party JS, no localStorage/sessionStorage, no persistent transcript, no history submission. **Each question is independent**, not a context-aware multi-turn conversation.
- Source extraction uses existing published/public search adapters only; digest/quote validation continues to return `verified=false`. Lack of sources abstains without a model call.

## Constraints and omissions

1. **Real provider API call: NOT EXECUTED.** No real credential supplied or retrieved, no live provider billing or integration test. Actual SDK parsing and JSON request layout verified with a mock HTTP transport only.
2. **No production-grade dependency locking.** `requirements-ai-phase-c-dev.txt` pins the optional SDK's direct packages for isolated development but is **not a complete audited hash-pinned lock**; all existing CI, production requirements and Render configurations remain untouched. Resolve, hash-lock, audit full transitive graph separately before activation.
3. **Citation presence != claim supported.** Exact quote/digest binding is not semantic/NLI verification. Generated drafts remain marked unverified.
4. Existing cache-based per-user request budget is only development-grade. No authenticated distributed monetary spending ledger, abuse detection or real provider usage accounting.
5. Source/publication/tenant boundary assumptions, prompt-injection evaluations, third-party provider data retention/privacy assessments and independent security review remain open.
6. Neither AI backend nor Chat UI activates in Staging/Production through this PR. No migrations, keys, services, branch-protection changes, model tools or agent actions.
7. Historical G4, STOP_340, HARD_STOP, C02, SC_07 and GOV_BREACH_01 findings and deploy controls are unchanged.

## Local test protocol

1. Use a clean isolated worktree based on the stated SHA. Never set a real `DATABASE_URL` or use any production connection/credential.
2. For optional SDK tests, create a dedicated local virtual environment and install only the dev pins: `python -m venv --system-site-packages .venv`; `.venv\\Scripts\\python.exe -m pip install --only-binary=:all: -r requirements-ai-phase-c-dev.txt`. Existing normal CI intentionally omits these optional packages.
3. Use local synthetic settings: `VORNEQ_ENV=development`, `DJANGO_SECRET_KEY=synthetic-test-only`, `DJANGO_DEBUG=1`, and local allowed hosts. Ensure `DATABASE_URL` is absent and `connection.vendor == "sqlite"`.
4. Compile existing gettext translations as CI does (Babel version from requirements-ci.lock), and run `python manage.py collectstatic --noinput` locally (ignored output). Then run `python manage.py check` and `python manage.py test apps.ai_core.tests apps.core.tests.test_home_i18n`.
5. `node --check assets/js/phase-c-chat.js` performs JavaScript syntax verification. Only the real SDK's **offline mock transport** is used in tests; CI has no provider keys or egress.
6. To display the development-preview UI without model calls, set both `VORNEQ_AI_PHASE_B_ENABLED=true` and `VORNEQ_AI_PHASE_C_ENABLED=true`, authenticate locally, and visit `/api/ai/v1/chat/?lang=fa`. With no provider credential/model, requests fail closed with a generic error.
7. Live development-model invocation requires an additional explicit owner decision and a separate provider key that is never logged or committed. Do not assume a configured SDK constitutes approval for a real external API call.

## Test and evidence interpretation

Local observation (2026-11-12): Python 3.12.10, Django 5.2.17, SQLite; `63/63` focused AI Core and Homepage i18n tests PASSED after matching CI preprocessing (`collectstatic`, compiling .po). SDK test uses an actual OpenAI SDK client with a fake `.invalid` origin caught by `httpx2.MockTransport`, exactly one synthetic request, **zero network egress**. `python -m compileall`, Django system check and `node --check` passed.

The official GitHub PR CI (including PostgreSQL, Security Audit, Backup Restore and Global Quality) is the only authority for broader regression claims. Normal CI may **skip the SDK-specific optional test** because OpenAI SDK is intentionally not in the immutable CI dependency lock; do not equate a skipped test with passed live-model validation.

## Final guard state

```text
PHASE_C_CODE=ISOLATED_DEVELOPMENT_PREVIEW
PHASE_B_OFFLINE_COMPATIBILITY=PRESERVED
OPENAI_SDK_STRUCTURED_PARSE=OFFLINE_MOCK_VERIFIED
LIVE_MODEL_EXECUTION=NOT_PERFORMED
SEMANTIC_GROUNDEDNESS=NOT_VERIFIED
CHAT_MEMORY=NONE
PRODUCTION_AI=DISABLED
STAGING_AI=DISABLED
MERGE=NOT_AUTHORIZED
DEPLOY=NOT_AUTHORIZED
```
