"""Network-free tests for the Resend email backend."""
import json
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from config.email_backends import ResendEmailBackend


class _Response:
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


@override_settings(DEFAULT_FROM_EMAIL="verified@example.com")
class ResendBackendTests(SimpleTestCase):
    def backend(self, **kwargs):
        with patch.dict("os.environ", {"RESEND_API_KEY": "test-secret"}):
            return ResendEmailBackend(**kwargs)

    def test_requires_api_key(self):
        with patch.dict("os.environ", {"RESEND_API_KEY": ""}):
            with self.assertRaises(ImproperlyConfigured):
                ResendEmailBackend()

    @patch("config.email_backends.urlopen", return_value=_Response())
    def test_plain_text(self, send):
        backend = self.backend()
        result = backend.send_messages([EmailMessage("Subject", "Body", to=["recipient@example.com"])])
        self.assertEqual(result, 1)
        request = send.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["text"], "Body")
        self.assertEqual(payload["to"], ["recipient@example.com"])
        self.assertEqual(send.call_args.kwargs["timeout"], 10)

    @patch("config.email_backends.urlopen", return_value=_Response())
    def test_html_alternative(self, send):
        msg = EmailMultiAlternatives("Subject", "Plain", to=["recipient@example.com"])
        msg.attach_alternative("<b>HTML</b>", "text/html")
        self.assertEqual(self.backend().send_messages([msg]), 1)
        self.assertEqual(json.loads(send.call_args.args[0].data)["html"], "<b>HTML</b>")

    @patch("config.email_backends.urlopen", side_effect=TimeoutError("test-secret"))
    def test_timeout_redacts_secret(self, send):
        with self.assertRaises(RuntimeError) as error:
            self.backend().send_messages([EmailMessage("S", "B", to=["r@example.com"])])
        self.assertNotIn("test-secret", str(error.exception))

    @patch("config.email_backends.urlopen", side_effect=OSError("test-secret"))
    def test_fail_silently(self, send):
        self.assertEqual(self.backend(fail_silently=True).send_messages(
            [EmailMessage("S", "B", to=["r@example.com"])]), 0)

    @patch("config.email_backends.urlopen", return_value=_Response())
    def test_attachments_rejected(self, send):
        msg = EmailMessage("S", "B", to=["r@example.com"])
        msg.attach("secret.txt", b"secret", "text/plain")
        with self.assertRaises(ValueError):
            self.backend().send_messages([msg])
        send.assert_not_called()
