# Persistent paid Staging image authorization

Default off. VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS=true is independent of
chat. Set it on the Staging web service and separately authorized image worker,
with VORNEQ_AI_DEPLOY_READ_TOKEN (repository-scoped Actions/Deployments read-only).
Both must run the latest officially owner-deployed successful Staging SHA. The
worker is not deployed automatically by this policy; owner deploys the same SHA
and retains its separate service identity, grant and paid switches. Legacy and
mock modes stay exact-SHA. No Production image authorization. Ledger rechecks
the runtime binding and continues to enforce independent staging-only image
account, allowance, per-request reservation ceiling and emergency stop.
VORNEQ_AI_IMAGE_STAGING_PREPAID_ONLY=true removes additional daily caps only.
No manual authorization per normal image after the owner grants ongoing use
and resumes the image account. No provider call, live activation, balance
increase or ledger resume is authorized by the code change itself.
