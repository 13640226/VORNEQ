# VORNEQ — AI Core + Global AI Phase A

**Base:** 89e046cdf61f1282a1c58a73f0d55dd4d03a90a8  
**Mode:** isolated development branch; no merge or deployment authorization.

## Implementation

- POST /api/ai/v1/ask/ is a session-authenticated, CSRF-protected JSON API; it returns 404 unless VORNEQ_ENV=development and VORNEQ_AI_CORE_ENABLED=true. The endpoint stays disabled by default.
- Question 1–200 chars, request body <=2 KiB; language must be fa/en/de; optional Boolean allow_model is per-request opt-in.
- Retrieval uses the existing UnifiedSearch service but **explicitly** selects public Article, Product, LibraryItem and Audio adapters. Private DocumentSearchAdapter and held MediaAsset are excluded; limit three results. Public-source title/excerpt size is bounded and URLs are restricted to local relative paths.
- Default mode is sources_only (or no_sources) and gives citation IDs S1–S3, without fabricating an AI answer. No DB migration, vector indexing, private retrieval or agent actions.
- Optional OpenAI Responses adapter uses pinned TLS endpoint api.openai.com/v1/responses, no redirects, no tools, store=false, 5s timeout, bounded request/output. External calls require ALL: development environment + server flags VORNEQ_AI_CORE_ENABLED and VORNEQ_AI_EXTERNAL_EGRESS_ENABLED + VORNEQ_AI_API_KEY and VORNEQ_AI_MODEL + authenticated request allow_model=true + at least one public source. No real key or API call is used in this PR.
- Untrusted excerpts are presented as data. A model draft must cite provided IDs; failures or unknown citations return source-only fallback. **Citation syntax does not establish claim accuracy**. Every draft is verified=false.
- API does not persist questions/answers; platform logging retention and privacy still require separate assessment.

## Local testing

Run python manage.py test apps.ai_core.tests with an isolated disposable SQLite DB and no external model secret. CI subsequently tests SQLite and PostgreSQL plus security/quality checks.

## Unresolved gates

Tenant-private RAG is NOT implemented. Independent source entailment verification, prompt-injection risk analysis, consent UX, abuse quotas/rate limiting, provider credential custody, production network egress control and audit policies need independent work.

PRODUCTION_AI_ACTIVATION=NO
STAGING_AI_ACTIVATION=NO
EXTERNAL_PROVIDER_DEFAULT=DISABLED
PRODUCTION_BRANCH_PROTECTION_GO=NO
MERGE=SEPARATE_SHA_BOUND_OWNER_DECISION_REQUIRED
DEPLOY=NO
