# Draft: persistent owner-deployment chat policy and prepaid-only Staging chat

Default behavior is unchanged. Optional chat-only settings:
VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=true, and a dedicated read-only
VORNEQ_AI_DEPLOY_READ_TOKEN (Actions and Deployments read permissions).
The running SHA must match the latest successful official owner-run Deploy
workflow and both deployment records for its environment. Stale releases,
missing evidence and API failures fail closed. Positive process cache is 60
seconds; failures 10 seconds. Requires the workflow head SHA to match the
deployed SHA (normal main deployment). The owner reference, service, model,
actor policy, feature flags, recovery and ledger remain checked separately.
No automatic deploy is triggered and #448 stays unchanged. To roll back,
disable the flag and restore the exact authorized SHA.

VORNEQ_AI_CHAT_STAGING_PREPAID_ONLY=true removes the extra daily Staging chat
ledger ceiling, only on authorized Staging chat. It requires the shared
ledger; no fallback to non-ledger chat. The total prepaid allowance, per-call
reservations, emergency stop and abuse throttling remain. Production already
uses the prepaid allowance without that daily ceiling. Image account limits
and image SHA policies remain unchanged. Provider billing is independent.
No live settings or balances changed. Review, CI and controlled deployment
and verification required before activation.
