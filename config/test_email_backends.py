"""Network-free Django tests for Resend HTTPS delivery."""
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from config.email_backends import EmailDeliveryError, ResendEmailBackend


class Response:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@override_settings(DEFAULT_FROM_EMAIL="verified@example.com")
class ResendBackendTests(SimpleTestCase):
    def backend(self, **kwargs):
        with patch.dict("os.environ", {"RESEND_API_KEY": "test-secret"}):
            return ResendEmailBackend(**kwargs)

    def message(self):
        return EmailMessage("Verify", "verification-link-secret", to=["recipient@example.com"])

    def test_missing_api_key(self):
        with patch.dict("os.environ", {"RESEND_API_KEY": ""}):
            with self.assertRaises(ImproperlyConfigured):
                ResendEmailBackend()

    @override_settings(RESEND_TIMEOUT_SECONDS=0)
    def test_invalid_timeout(self):
        with self.assertRaises(ImproperlyConfigured):
            self.backend()

    @patch("config.email_backends.urlopen", return_value=Response(202))
    def test_plain_text_success(self, send):
        self.assertEqual(self.backend().send_messages([self.message()]), 1)
        request = send.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["text"], "verification-link-secret")
        self.assertEqual(payload["to"], ["recipient@example.com"])
        self.assertEqual(payload["from"], "verified@example.com")
        self.assertEqual(send.call_args.kwargs["timeout"], 10)
        self.assertEqual(request.full_url, "https://api.resend.com/emails")

    @patch("config.email_backends.urlopen", return_value=Response(200))
    def test_html_allauth_style(self, send):
        msg = EmailMultiAlternatives("Verify", "Plain link", to=["recipient@example.com"])
        msg.attach_alternative("<a href='https://example.com/verify'>Verify</a>", "text/html")
        self.assertEqual(self.backend().send_messages([msg]), 1)
        self.assertIn("Verify</a>", json.loads(send.call_args.args[0].data)["html"])

    @patch("config.email_backends.urlopen")
    def test_no_recipient_is_not_counted(self, send):
        self.assertEqual(self.backend().send_messages([EmailMessage("S", "B", to=[])]), 0)
        send.assert_not_called()

    @patch("config.email_backends.urlopen", side_effect=TimeoutError("test-secret"))
    def test_timeout_is_redacted(self, send):
        with self.assertRaises(EmailDeliveryError) as caught:
            self.backend().send_messages([self.message()])
        self.assertEqual(caught.exception.category, "network")
        self.assertNotIn("test-secret", str(caught.exception))
        self.assertNotIn("verification-link-secret", str(caught.exception))

    @patch("config.email_backends.urlopen", side_effect=URLError("test-secret"))
    def test_network_failure(self, send):
        with self.assertRaises(EmailDeliveryError) as caught:
            self.backend().send_messages([self.message()])
        self.assertEqual(caught.exception.category, "network")

    @patch("config.email_backends.urlopen", side_effect=HTTPError("https://api.resend.com/emails", 400, "test-secret", None, None))
    def test_http_400(self, send):
        with self.assertRaises(EmailDeliveryError) as caught:
            self.backend().send_messages([self.message()])
        self.assertEqual(caught.exception.status, 400)
        self.assertNotIn("test-secret", str(caught.exception))

    @patch("config.email_backends.urlopen", side_effect=HTTPError("https://api.resend.com/emails", 401, "test-secret", None, None))
    def test_http_401(self, send):
        with self.assertRaises(EmailDeliveryError) as caught:
            self.backend().send_messages([self.message()])
        self.assertEqual(caught.exception.status, 401)

    @patch("config.email_backends.urlopen", side_effect=HTTPError("https://api.resend.com/emails", 429, "test-secret", None, None))
    def test_http_429(self, send):
        with self.assertRaises(EmailDeliveryError) as caught:
            self.backend().send_messages([self.message()])
        self.assertEqual(caught.exception.status, 429)

    @patch("config.email_backends.urlopen", side_effect=HTTPError("https://api.resend.com/emails", 500, "test-secret", None, None))
    def test_http_500(self, send):
        with self.assertRaises(EmailDeliveryError) as caught:
            self.backend().send_messages([self.message()])
        self.assertEqual(caught.exception.status, 500)

    @patch("config.email_backends.urlopen", return_value=Response(503))
    def test_non_2xx_response(self, send):
        with self.assertRaises(EmailDeliveryError) as caught:
            self.backend().send_messages([self.message()])
        self.assertEqual(caught.exception.status, 503)

    @patch("config.email_backends.urlopen", side_effect=OSError("test-secret"))
    def test_fail_silently(self, send):
        self.assertEqual(self.backend(fail_silently=True).send_messages([self.message()]), 0)

    @patch("config.email_backends.urlopen", side_effect=OSError("test-secret"))
    def test_fail_loudly(self, send):
        with self.assertRaises(EmailDeliveryError):
            self.backend(fail_silently=False).send_messages([self.message()])

    @patch("config.email_backends.urlopen")
    def test_attachment_rejected(self, send):
        msg = self.message()
        msg.attach("private.txt", b"secret", "text/plain")
        with self.assertRaises(EmailDeliveryError) as caught:
            self.backend().send_messages([msg])
        self.assertEqual(caught.exception.category, "unsupported_message")
        send.assert_not_called()

    @patch("config.email_backends.urlopen")
    def test_unsupported_alternative_rejected(self, send):
        msg = EmailMultiAlternatives("S", "B", to=["recipient@example.com"])
        msg.attach_alternative("data", "text/calendar")
        with self.assertRaises(EmailDeliveryError):
            self.backend().send_messages([msg])
        send.assert_not_called()

    @patch("config.email_backends.urlopen", return_value=Response(202))
    def test_to_cc_reply_to_preserved(self, send):
        msg = EmailMessage("S", "B", to=["to@example.com"],
                           cc=["cc@example.com"], reply_to=["reply@example.com"])
        self.assertEqual(self.backend().send_messages([msg]), 1)
        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(payload["to"], ["to@example.com"])
        self.assertEqual(payload["cc"], ["cc@example.com"])
        self.assertEqual(payload["reply_to"], ["reply@example.com"])

    @patch("config.email_backends.urlopen", return_value=Response(202))
    def test_bcc_is_never_visible_to_other_recipients(self, send):
        msg = EmailMessage("S", "B", to=["to@example.com"],
                           cc=["cc@example.com"], bcc=["hidden@example.com"])
        self.assertEqual(self.backend().send_messages([msg]), 1)
        self.assertEqual(send.call_count, 2)
        visible = json.loads(send.call_args_list[0].args[0].data)
        hidden = json.loads(send.call_args_list[1].args[0].data)
        self.assertEqual(visible["to"], ["to@example.com"])
        self.assertEqual(visible["cc"], ["cc@example.com"])
        self.assertNotIn("hidden@example.com", json.dumps(visible))
        self.assertEqual(hidden["to"], ["hidden@example.com"])
        self.assertNotIn("cc", hidden)
        self.assertNotIn("to@example.com", json.dumps(hidden))

    @patch("config.email_backends.urlopen", return_value=Response(202))
    def test_bcc_only_is_separate(self, send):
        msg = EmailMessage("S", "B", bcc=["first@example.com", "second@example.com"])
        self.assertEqual(self.backend().send_messages([msg]), 1)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(json.loads(send.call_args_list[0].args[0].data)["to"], ["first@example.com"])
        self.assertEqual(json.loads(send.call_args_list[1].args[0].data)["to"], ["second@example.com"])

    @patch("config.email_backends.urlopen")
    def test_bcc_partial_failure_does_not_claim_success(self, send):
        send.side_effect = [Response(202), HTTPError("https://api.resend.com/emails", 500, "error", None, None)]
        msg = EmailMessage("S", "B", to=["to@example.com"], bcc=["hidden@example.com"])
        with self.assertRaises(EmailDeliveryError):
            self.backend().send_messages([msg])
        self.assertEqual(send.call_count, 2)

    @patch("config.email_backends.urlopen")
    def test_partial_failure_fail_silently_returns_zero_without_retry(self, send):
        send.side_effect = [Response(202), HTTPError("https://api.resend.com/emails", 429, "rate limit", None, None)]
        msg = EmailMessage("S", "B", to=["visible@example.com"], bcc=["hidden@example.com"])
        self.assertEqual(self.backend(fail_silently=True).send_messages([msg]), 0)
        self.assertEqual(send.call_count, 2)

    @patch("config.email_backends.urlopen", return_value=Response(202))
    def test_multiple_bcc_addresses_are_not_shared(self, send):
        msg = EmailMessage("S", "B", to=["visible@example.com"],
                           bcc=["hidden1@example.com", "hidden2@example.com"])
        self.assertEqual(self.backend().send_messages([msg]), 1)
        self.assertEqual(send.call_count, 3)
        bodies = [json.loads(call.args[0].data) for call in send.call_args_list]
        self.assertEqual(bodies[0]["to"], ["visible@example.com"])
        self.assertEqual(bodies[1]["to"], ["hidden1@example.com"])
        self.assertEqual(bodies[2]["to"], ["hidden2@example.com"])
        for index, body in enumerate(bodies):
            for other in range(len(bodies)):
                if index != other:
                    self.assertNotIn(bodies[other]["to"][0], json.dumps(body))

    @override_settings(EMAIL_BACKEND="config.email_backends.ResendEmailBackend")
    @patch("config.email_backends.urlopen", return_value=Response(202))
    def test_allauth_confirmation_template_through_https_backend(self, send):
        from allauth.account.adapter import get_adapter
        from django.contrib.sites.models import Site
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        request.site = Site(domain="example.com", name="Example")
        with patch.dict("os.environ", {"RESEND_API_KEY": "test-secret"}):
            get_adapter(request).send_mail(
                "account/email/email_confirmation_signup",
                "recipient@example.com",
                {"user": None, "activate_url": "https://example.com/confirm/fake-token"},
            )
        self.assertTrue(send.called)
        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(payload["to"], ["recipient@example.com"])
        self.assertIn("https://example.com/confirm/fake-token", payload["text"])

    @override_settings(EMAIL_BACKEND="config.email_backends.ResendEmailBackend")
    @patch("config.email_backends.urlopen", return_value=Response(202))
    def test_allauth_password_reset_template_through_https_backend(self, send):
        from allauth.account.adapter import get_adapter
        from django.contrib.sites.models import Site
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        request.site = Site(domain="example.com", name="Example")
        with patch.dict("os.environ", {"RESEND_API_KEY": "test-secret"}):
            get_adapter(request).send_mail(
                "account/email/password_reset_key",
                "recipient@example.com",
                {"user": None, "password_reset_url": "https://example.com/reset/fake-token"},
            )
        self.assertTrue(send.called)
        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(payload["to"], ["recipient@example.com"])
        self.assertIn("https://example.com/reset/fake-token", payload["text"])
