# Staging HTTPS email backend (Draft PR; not deployed)

This change adds `config.email_backends.ResendEmailBackend` without activating it.

Activation requires **separate authorization** and:
- A verified sender domain and approved sender address.
- Render secret `RESEND_API_KEY` (never commit or print its value).
- Render environment variable `EMAIL_BACKEND=config.email_backends.ResendEmailBackend`.
- Existing `DEFAULT_FROM_EMAIL` must identify a verified sender.
- Preserve mandatory account verification; do not enable console/dummy backends.
- Do not change `DATABASE_URL`, Blueprint Auto Sync, or migration behavior.

The backend uses HTTPS POST to Resend, one request per Django email message,
with a 10-second timeout and no request/response content logging.
It supports plain text and HTML alternatives; attachments are explicitly rejected.
No retry is performed to avoid duplicate transactional messages.

Before any deployment: run the network-free unit tests, review domain verification,
obtain explicit authorization for Render environment changes and deploy, then
test signup verification and password reset using an authorized staging test account.
Observe 5xx and /health/ before declaring success.

Rollback requires separately authorized restoration of the previous deployed code
and EMAIL_BACKEND setting. Note that the previous SMTP route was already failing,
so rollback does not guarantee working email delivery.
