# Global AI Staging unlimited mode ? proposal only

**Default:** OFF. **Scope:** Staging only. **No deploy, no flag changes in this PR.**

- `VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=true` bypasses only the Global AI Redis request quota in Staging.
- The separate `VORNEQ_AI_STAGING_UNMETERED=true` bypasses the staging PostgreSQL reservation limit and its daily request limit.
- Both flags are separate, default OFF, and require explicit owner approval before changing Render.
- Existing login, CSRF, staff/superuser allowlist, SHA/service pinning, SSRF protections, input validation, timeouts, and provider output token limits remain.
- Global AI remains disabled unless `VORNEQ_GLOBAL_AI_ENABLED=true` is separately authorized.
- **OpenAI project spend limit ($2 currently) cannot be removed by this repository change.** It must be reviewed and changed in the provider project, with an explicit decision on potentially unbounded spend.
- Removing all request quotas increases abuse, denial-of-service, cost, and availability risks. Keep an emergency kill switch and monitoring.
- **No Production enablement.** Never deploy this feature in Production without a separate security design.
- Run isolated offline tests and official CI; assess the result before any merge, deployment, or live provider calls.
