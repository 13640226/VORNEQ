"""Django email backend for Resend's HTTPS API (opt-in only)."""
import json
import logging
import math
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Safe, classified delivery failure; never contains provider response bodies."""

    def __init__(self, category, status=None):
        self.category = category
        self.status = status
        label = f"Email delivery failed ({category})"
        if status is not None:
            label += f" [HTTP {status}]"
        super().__init__(label)


class ResendEmailBackend(BaseEmailBackend):
    """Send Django text/HTML messages using HTTPS; no automatic retries."""

    endpoint = "https://api.resend.com/emails"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = os.environ.get("RESEND_API_KEY", "")
        if not self.api_key:
            raise ImproperlyConfigured("RESEND_API_KEY is required for the HTTPS email backend")
        self.timeout = getattr(settings, "RESEND_TIMEOUT_SECONDS", 10)
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not math.isfinite(self.timeout)
            or not 0 < self.timeout <= 30
        ):
            raise ImproperlyConfigured("RESEND_TIMEOUT_SECONDS must be between 0 and 30")

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for message in email_messages:
            try:
                if self._send(message):
                    sent += 1
            except Exception as exc:
                if self.fail_silently:
                    logger.error("Email delivery failed (details suppressed)")
                    continue
                if isinstance(exc, EmailDeliveryError):
                    raise
                if isinstance(exc, HTTPError):
                    raise EmailDeliveryError("http", exc.code) from None
                if isinstance(exc, (TimeoutError, URLError, OSError)):
                    raise EmailDeliveryError("network") from None
                if isinstance(exc, ValueError):
                    raise EmailDeliveryError("unsupported_message") from None
                raise EmailDeliveryError("unexpected") from None
        return sent

    def _send(self, message):
        to = list(message.to or [])
        cc = list(message.cc or [])
        bcc = list(message.bcc or [])
        if not (to or cc or bcc):
            return False
        if message.attachments:
            raise ValueError("Attachments unsupported")
        html = None
        if isinstance(message, EmailMultiAlternatives):
            for body, mimetype in message.alternatives:
                if mimetype == "text/html":
                    if html is not None:
                        raise ValueError("Multiple HTML alternatives unsupported")
                    html = body
                else:
                    raise ValueError("Unsupported alternative")
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "subject": message.subject,
            "text": message.body,
        }
        if html is not None:
            payload["html"] = html
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        # Bcc recipients never share an API request with visible recipients.
        # Partial delivery can occur if a later request fails; do not retry.
        if to or cc:
            visible = dict(payload, to=to or cc)
            if to and cc:
                visible["cc"] = cc
            self._post(visible)
        for recipient in bcc:
            self._post(dict(payload, to=[recipient]))
        return True

    def _post(self, payload):
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        # Never log request headers, response bodies, recipients, or email content.
        with urlopen(request, timeout=self.timeout) as response:
            status = response.status
            if not 200 <= status < 300:
                raise EmailDeliveryError("http", status)
