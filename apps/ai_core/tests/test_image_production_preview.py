"""Production image preview must remain UI-only and deny unauthorized users."""
import os
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.ai_core.image_generation.page import production_studio_preview_allowed


class ProductionImagePreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin1 = User.objects.create_user(username="image-prod-admin1", is_staff=True, is_superuser=True)
        User.objects.create_user(username="image-prod-reserved2", is_staff=True, is_superuser=True)
        cls.admin3 = User.objects.create_user(username="image-prod-admin3", is_staff=True, is_superuser=True)
        cls.other = User.objects.create_user(username="image-prod-other", is_staff=True, is_superuser=True)

    def test_allowlist_and_read_only(self):
        with override_settings(VORNEQ_ENV="production", DEBUG=False,
                               VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED=True,
                               VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=False,
                               VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=False), patch.dict(os.environ, {
                                   "RENDER_SERVICE_ID": "srv-dadn07eq1p3s73eccau0"}):
            for user in (self.admin1, self.admin3):
                # Database PKs in this isolated test are 1 and 3; both are allowlisted.
                expected = user.pk in (1, 3)
                self.assertEqual(production_studio_preview_allowed(user), expected)
                self.client.force_login(user)
                response = self.client.get(reverse("ai_core:image-studio"))
                self.assertEqual(response.status_code, 200 if expected else 404)
                if expected:
                    self.assertContains(response, "Production preview")
                    self.assertNotContains(response, 'data-vq-image-studio')
                    self.assertNotContains(response, 'images/jobs/')
                    self.assertIn("no-store", response["Cache-Control"])
            self.assertFalse(production_studio_preview_allowed(self.other))

    def test_disabled_by_default_and_wrong_service(self):
        self.client.force_login(self.admin1)
        with override_settings(VORNEQ_ENV="production", DEBUG=False,
                               VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED=False), patch.dict(os.environ, {
                                   "RENDER_SERVICE_ID": "srv-dadn07eq1p3s73eccau0"}):
            self.assertEqual(self.client.get(reverse("ai_core:image-studio")).status_code, 404)
        with override_settings(VORNEQ_ENV="production", DEBUG=False,
                               VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED=True), patch.dict(os.environ, {
                                   "RENDER_SERVICE_ID": "srv-dbm7dvc9v7es7393g70g"}):
            self.assertEqual(self.client.get(reverse("ai_core:image-studio")).status_code, 404)

    def test_preview_denies_non_privileged_and_inactive_users(self):
        """A matching numeric ID alone must not grant Production preview."""
        with override_settings(VORNEQ_ENV="production", DEBUG=False,
                               VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED=True), patch.dict(os.environ, {
                                   "RENDER_SERVICE_ID": "srv-dadn07eq1p3s73eccau0"}):
            original = (self.admin1.is_staff, self.admin1.is_superuser, self.admin1.is_active)
            try:
                for field in ("is_staff", "is_superuser", "is_active"):
                    setattr(self.admin1, field, False)
                    self.assertFalse(production_studio_preview_allowed(self.admin1))
                    self.client.force_login(self.admin1)
                    self.assertEqual(self.client.get(reverse("ai_core:image-studio")).status_code, 404)
                    setattr(self.admin1, field, True)
            finally:
                self.admin1.is_staff, self.admin1.is_superuser, self.admin1.is_active = original
