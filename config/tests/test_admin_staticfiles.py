"""Regression coverage for the custom Django Admin stylesheet."""

from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


class AdminStaticfilesTests(SimpleTestCase):
    def test_custom_admin_stylesheet_is_discoverable(self):
        stylesheet = finders.find("admin/css/vorneq_admin.css")
        self.assertIsNotNone(stylesheet)
        self.assertEqual(
            Path(stylesheet).resolve(),
            (settings.BASE_DIR / "static" / "admin" / "css" / "vorneq_admin.css").resolve(),
        )
        self.assertNotEqual(Path(stylesheet).resolve(), Path(settings.STATIC_ROOT).resolve())