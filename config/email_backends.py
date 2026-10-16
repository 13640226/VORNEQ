"""Django email backend using Resend's HTTPS API.

Only enable this backend after the sender domain and API key are configured.
"""
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Send one Django message per HTTPS request, without logging email contents."""

    endpoint = "https://api.resend.com/emails"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = os.environ.get("RESEND_API_KEY", "")
        self.timeout = getattr(settings, "RESEND_TIMEOUT_SECONDS", 10)
        if not self.api_key:
            raise ImproperlyConfigured("RESEND_API_KEY is required for the HTTPS email backend")

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
            except Exception as exc:
                if self.fail_silently:
                    logger.error("Email delivery failed (details suppressed)")
                    continue
                if isinstance(exc, ValueError):
                    raise
                raise RuntimeError("Email delivery failed; see secure provider diagnostics") from None
            sent += 1
        return sent

    def _send(self, message):
        if message.attachments:
            raise ValueError("Email attachments are not supported by this backend")
        if not message.recipients():
            return
        html_parts = []
        if isinstance(message, EmailMultiAlternatives):
            for body, mimetype in message.alternatives:
                if mimetype == "text/html":
                    html_parts.append(body)
                else:
                    raise ValueError("Unsupported email alternative type")
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": message.recipients(),
            "subject": message.subject,
            "text": message.body,
        }
        if html_parts:
            payload["html"] = html_parts[-1]
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        # Do not log request headers, response body, email addresses or provider errors.
        with urlopen(request, timeout=self.timeout) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError("Email provider returned an unsuccessful response")
