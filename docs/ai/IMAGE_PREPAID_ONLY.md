# Paid Staging image prepaid-only mode (default off)

Set VORNEQ_AI_IMAGE_STAGING_PREPAID_ONLY=true on both the authorized web
and paid worker only after CI, controlled deployment and separate owner
authorization. No daily submission counts or additional daily ledger ceiling
in this mode. Actual cost still reserved before each call against the dedicated
image allowance, with independently checked runtime/account identity, staging-only
account, model, per-request ceiling, emergency stop, safety identifier, durable
storage, per-minute throttle and idempotency. Default, mock, chat and Production
behavior unchanged. No existing quota, reservation, job or balance is reset.
Existing image SHA authorization stays exact on both services. Production image
engine is not yet implemented by this change. No live activation or paid call
is authorized by the code change. A rejected/uncertain request is not retried.
