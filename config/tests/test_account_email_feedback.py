from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.templatetags.static import static
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils.translation import override

from config.account_views import AccountEmailView
from config.email_backends import EmailDeliveryError


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountEmailFeedbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = get_user_model().objects.create_user(username="email-feedback", email="feedback@example.test", password="synthetic-test-password")
        EmailAddress.objects.update_or_create(user=self.user, email=self.user.email, defaults={"primary": True, "verified": False})
        self.client.force_login(self.user)

    def send(self, **fields):
        return self.client.post(reverse("account_email"), {"email": self.user.email, "action_send": "", **fields}, follow=True)

    def test_real_allauth_success_message_and_single_mail(self):
        with override("en"):
            self.assertIs(resolve(reverse("account_email")).func.view_class, AccountEmailView)
            response = self.send()
            self.assertContains(response, "account-email-notice--info")
            self.assertContains(response, self.user.email)
            self.assertEqual(len(mail.outbox), 1)
            self.assertFalse(EmailAddress.objects.get(user=self.user, email=self.user.email).verified)

    @override_settings(ACCOUNT_RATE_LIMITS={"confirm_email": "1/180s/key"})
    def test_real_rate_limit_does_not_send_twice(self):
        with override("en"):
            self.assertContains(self.send(), "account-email-notice--info")
            response = self.send()
            self.assertContains(response, "No new verification email was sent.")
            self.assertNotContains(response, "account-email-notice--info")
            self.assertEqual(len(mail.outbox), 1)

    @patch("allauth.account.views.send_verification_email_to_address", return_value=False)
    def test_no_send_is_warning_not_success(self, send):
        with override("en"):
            response = self.send()
            self.assertContains(response, "No new verification email was sent.")
            self.assertContains(response, "account-email-notice--warning")
            self.assertNotContains(response, "account-email-notice--info")
            self.assertEqual(len(mail.outbox), 0)
            send.assert_called_once()

    @patch("allauth.account.models.EmailAddress.send_confirmation", side_effect=EmailDeliveryError("http", 403))
    def test_provider_failure_has_safe_error(self, send):
        with override("en"):
            response = self.send()
            self.assertContains(response, "Unable to send the verification email.")
            self.assertContains(response, "account-email-notice--error")
            self.assertNotContains(response, "HTTP 403")
            self.assertNotContains(response, "account-email-notice--info")
            self.assertEqual(len(mail.outbox), 0)
            send.assert_called_once()

    @patch("allauth.account.views.send_verification_email_to_address")
    def test_foreign_address_and_missing_selection_do_not_send(self, send):
        other = get_user_model().objects.create_user(username="email-other", email="other@example.test")
        EmailAddress.objects.update_or_create(user=other, email=other.email, defaults={"primary": True, "verified": False})
        with override("en"):
            self.assertContains(self.send(email=other.email), "No new verification email was sent.")
            self.assertContains(self.send(email=""), "Choose an email address before sending verification.")
            send.assert_not_called()

    def test_csrf_and_authentication_preserved(self):
        with override("en"):
            url = reverse("account_email")
            client = Client(enforce_csrf_checks=True)
            client.force_login(self.user)
            self.assertEqual(client.post(url, {"email": self.user.email, "action_send": ""}).status_code, 403)
            self.assertEqual(Client().get(url).status_code, 302)

    def test_loading_markup_three_languages(self):
        for lang in ("en", "de", "fa"):
            with self.subTest(lang=lang), override(lang):
                response = self.client.get(reverse("account_email"))
                self.assertContains(response, "data-email-resend")
                self.assertContains(response, "data-email-progress")
                self.assertContains(response, static("js/account-email-verification.js"))
                self.assertContains(response, "name=\"csrfmiddlewaretoken\"")
                if lang != "en":
                    self.assertNotContains(response, "Sending verification email...")
