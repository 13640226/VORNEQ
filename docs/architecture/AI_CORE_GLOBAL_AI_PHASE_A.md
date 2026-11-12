# VORNEQ — Offline AI Core + Global AI Phase A (provider-separated)

**Initial base:** 89e046cdf61f1282a1c58a73f0d55dd4d03a90a8
**Scope:** Offline/public retrieval only. No real LLM provider, provider credential, model execution, egress toggle, or external model request is included in this PR.

## Implementation

- `POST /api/ai/v1/ask/`: session-authenticated, CSRF-protected, JSON-only. Returns 404 unless `VORNEQ_ENV=development` and `VORNEQ_AI_CORE_ENABLED=true`; defaults off and never enabled on staging/production.
- Question 1–200 printable characters, request body <=2 KiB; language must be fa/en/de. Allowed request fields: `question`, `language`. Any `allow_model`, `provider`, `tools` or other extra field is rejected with HTTP 400.
- Explicit public ArticleAdapter, ProductAdapter, LibraryItemAdapter and AudioItemAdapter. Private Documents and held MediaAsset are not queried. At most 3 bounded citation records, relative URLs only.
- Response mode is `sources_only` or `no_sources`, `verified=false`, `model_status=offline_only`. There is no model draft path and no response fabrication when sources are empty.
- No migrations, vector indexing, private retrieval, agent actions, or production config changes. No real API keys or network provider calls in this PR.
- Source excerpts are untrusted data; citations indicate identifiers, not independent truth verification.
- API does not deliberately persist questions/answers; existing platform observability, rate limiting and privacy still require review.

## Separated provider

The former `apps/ai_core/provider.py` (OpenAI Responses HTTP adapter), provider imports and model-enablement settings were **removed from this PR**. An actual external provider is deferred to a separately authorized branch, policy contract, threat model, independent security review, credential custody, explicit opt-in and egress controls. The removed implementation must not be treated as approved or validated for reuse.

## Tests and governance

- Run `python manage.py test apps.ai_core.tests` against disposable local SQLite without external provider credentials; GitHub CI is authoritative for broader workflows.
- Merge and deployment require separate approvals. 15 local tests on the earlier adapter-containing head were **not** acceptance evidence for this modified head.
- Independent security review, source/publication/tenant checks, abuse/rate controls and existing repository governance findings remain open until separately resolved.

PRODUCTION_AI_ACTIVATION=NO
STAGING_AI_ACTIVATION=NO
EXTERNAL_PROVIDER_INCLUDED=NO
BRANCH_PROTECTION_GO=NO
MERGE=SEPARATE_SHA_BOUND_OWNER_DECISION_REQUIRED
DEPLOY=NO
