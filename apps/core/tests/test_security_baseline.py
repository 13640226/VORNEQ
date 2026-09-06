from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class SecurityHeaderTests(TestCase):
    def test_home_emits_baseline_security_headers(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(
            response.headers["Referrer-Policy"],
            "strict-origin-when-cross-origin",
        )

        policy = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertIn("form-action 'self'", policy)


class AuthenticationSecurityContractTests(TestCase):
    def test_allauth_rate_limits_are_explicit(self):
        self.assertEqual(settings.ACCOUNT_RATE_LIMITS["login"], "20/m/ip")
        self.assertEqual(
            settings.ACCOUNT_RATE_LIMITS["login_failed"],
            "10/m/ip,5/5m/key",
        )
        self.assertEqual(settings.ACCOUNT_RATE_LIMITS["signup"], "5/10m/ip")
        self.assertEqual(
            settings.ACCOUNT_RATE_LIMITS["reset_password"],
            "5/15m/ip,3/15m/key",
        )

    def test_axes_lockout_contract_remains_enabled(self):
        self.assertTrue(settings.AXES_ENABLED)
        self.assertEqual(settings.AXES_FAILURE_LIMIT, 5)
        self.assertEqual(
            settings.AXES_LOCKOUT_PARAMETERS,
            [["username", "ip_address"]],
        )

    def test_proxy_trust_is_opt_in_by_default(self):
        self.assertEqual(settings.ALLAUTH_TRUSTED_PROXY_COUNT, 0)
        self.assertIsNone(settings.ALLAUTH_TRUSTED_CLIENT_IP_HEADER)
