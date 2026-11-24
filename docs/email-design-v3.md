# Email design V3

Central design for all transactional e-mails (account and security), replacing the V2 inline layout.

- Layout: `templates/email/base.html` (HTML, table based, inline styles, MSO fallbacks, mobile media query) and `templates/email/base.txt` (plain text). The CTA button and link fallback live in `templates/email/_button.html`.
- Copy: `apps/core/email_strings.py` holds every string in `fa`, `de`, `en`; templates use `{% vq_mail "key" %}` from `apps/core/templatetags/vq_email.py`. Unsupported languages fall back to English; only Persian renders RTL.
- Logo: `static/email/vorneq-logo.png`, rendered from the official `horizontal.svg` by `scripts/build_email_logo.py` (Gmail/Outlook do not render SVG). Colours: `#2563EB` (symbol), `#0B1120` (wordmark and text).
- Covered messages (those the current allauth configuration sends): e-mail confirmation (login and signup), password reset, account-already-exists and unknown-account (both used because `ACCOUNT_PREVENT_ENUMERATION` is on). Notification mails (password changed, e-mail changed, ...) are not enabled in settings and therefore not templated yet.
- Tests: `apps/core/tests/test_email_design_v3.py`.
- Not part of this change: persisting each user's preferred language (separate PR) and SMTP delivery.