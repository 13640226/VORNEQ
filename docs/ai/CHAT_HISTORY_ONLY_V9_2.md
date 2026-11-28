# Chat V9.2 — independent history mode

When Conversations is enabled, the conversation actor policy admits an active
authenticated user, and the runtime identity is valid, saved history can be
opened without Global AI, a provider credential, a ledger reservation or a paid
release. Feedback still requires its own flag and the existing owner-scoped API.
The existing paid/legacy authorization and message endpoints are unchanged.
If paid generation is not authorized, the page has an inert hidden composer,
no model endpoint, no examples, no voice scripts, no streaming or recovery.
The JS submission path also rejects history-only mode before creating a
conversation or sending a request. Existing history mutations remain local.
No migration, environment change, live test or deployment is authorized here.
Production uses its own runtime identity; feature rollout is separate.
