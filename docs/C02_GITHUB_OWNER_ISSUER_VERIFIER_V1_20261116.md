# C02: independent GitHub owner release verifier V1 (2026-11-16)

**Documentary/implementation review only.** The Production write gate stays OFF. No actual owner-issued release or Migration GO is created by this document.

## Independent owner authorization boundary

The SHA-bound environment string remains a locator, not an authorization. The verifier obtains the owner comment through the fixed, authenticated GitHub REST HTTPS endpoint, pinned to repository 13640226/VORNEQ and issue #407. It requires a separately provisioned narrowly-scoped GitHub read token. No token is installed by this change.

The validated comment must have the exact owner account login 13640226 and numeric ID 199411505, an OWNER association, matching API/HTML URLs and issue number, unchanged creation/update timestamps, an explicit migration decision and operational Render identity risk acceptance, and a maximum fifteen-minute lifetime. The exact 40-character SHA, service ID, PostgreSQL resource ID, DB name, authenticated login, execution role, two ordered ai_core migrations, restored backup SHA256, and backup evidence reference must agree. Unexpected or duplicate JSON fields, metadata edits, revocations by deletion, wrong actor, expired comments, non-200 GitHub API responses, redirects, API timeouts and missing tokens all fail closed. No URL or token is printed.

## Future comment body contract — placeholder, NOT an issued authorization

Header line: C02_OWNER_MIGRATION_RELEASE_V1

Second line: one JSON object with **exact** keys and values matching the live parameters: decision=AUTHORIZE_PRODUCTION_AI_CORE_0001_0002, release_id, sha, service_id, postgres_id, database, session_user, current_user, migrations (exactly ai_core.0001_initial and ai_core.0002_aichatrequestguard), backup_sha256, backup_evidence, expires_at (UTC seconds Z, not more than 15 minutes after GitHub comment creation) and risk_acceptance=ACCEPT_RENDER_OPERATIONAL_IDENTITY_LIMIT.

Environment inputs needed for future separately authorized execution:
- VORNEQ_C02_MIGRATION_AUTH: old structured SHA-bound string; *not sufficient alone*.
- VORNEQ_C02_OWNER_COMMENT_ID: numeric GitHub owner comment identifier.
- VORNEQ_C02_GITHUB_READ_TOKEN: narrow read-only token for GitHub issue comments, never committed.
- VORNEQ_C02_BACKUP_SHA256 and VORNEQ_C02_BACKUP_EVIDENCE: exact reference identifiers.

The Runner independently re-fetches at initial authorization, immediately before one-use receipt consumption and just before commit, aborting if the body or metadata changes. The receipt remains durable if migration rolls back. Isolated negative tests include expired, edited, fake issuer, deleted, missing token, wrong scope, wrong SHA/DB/role/backup, failure before consumption, and revocation after consumption. Production-write flag remains False.

## Still open — not a Migration GO

- Point-of-use backup provenance and restore reference are not independently fetched by this module; equality to owner comment alone does not establish a fresh backup.
- Operational Render HMAC and same-session identity are not cryptographic PostgreSQL-backend resource proof.
- STOP_340 authority precedence, one-use owner decision, and acceptance of residual source-identity risk are not yet granted.
- Production GitHub Environment has no required reviewer gate. No scoped read-only GitHub token has been installed in Production.
- No GitHub-to-Render automated dispatcher has been configured; private One-Off Job read-only proof is independent.

Production: PRODUCTION_WRITE_ENABLED=False; C02=OPEN_CRITICAL; MIGRATION_GO=NO. No Deploy, DB mutation or migration is authorized.
