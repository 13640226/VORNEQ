import os
import subprocess
import sys

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class FoundationTests(TestCase):
    def test_test_settings_are_loaded(self):
        self.assertEqual(settings.SETTINGS_MODULE, "config.settings.test")
        self.assertIn("library", settings.INSTALLED_APPS)
        self.assertIn("marketplace", settings.INSTALLED_APPS)

    def test_home_url(self):
        url = reverse("home")
        self.assertEqual(url, "/fa/")
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_requires_authentication(self):
        url = reverse("admin:index")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('admin:login')}?next={url}",
        )


class ProductionSettingsTests(TestCase):
    @staticmethod
    def _import_production(**updates):
        env = os.environ.copy()
        for name in (
            "DJANGO_SETTINGS_MODULE",
            "DJANGO_SECRET_KEY",
            "DJANGO_DEBUG",
            "DJANGO_ALLOWED_HOSTS",
        ):
            env.pop(name, None)
        env.update(updates)
        return subprocess.run(
            [sys.executable, "-c", "import config.settings.production"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_missing_secret_key_fails(self):
        result = self._import_production(
            DJANGO_DEBUG="false",
            DJANGO_ALLOWED_HOSTS="example.com",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_enabled_debug_fails(self):
        result = self._import_production(
            DJANGO_SECRET_KEY="production-test-secret",
            DJANGO_DEBUG="yes",
            DJANGO_ALLOWED_HOSTS="example.com",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_DEBUG", result.stderr)

    def test_missing_allowed_hosts_fails(self):
        result = self._import_production(
            DJANGO_SECRET_KEY="production-test-secret",
            DJANGO_DEBUG="false",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)
