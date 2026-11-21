"""Staging Image Studio: fail-closed, no paid network, safe one-shot UI contract."""
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from apps.ai_core.image_generation.page import LABELS

BASE_SHA = "49016185eaa78a4b932ff003feb9f7925ff963c6"
STAGING_ID = "srv-dbm7dvc9v7es7393g70g"

ASSETS = Path(settings.BASE_DIR) / "assets"
JS = (ASSETS / "js" / "image-studio.js").read_text(encoding="utf-8")
CSS = (ASSETS / "css" / "image-studio.css").read_text(encoding="utf-8")


class ImageStudioPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="image-studio-owner", password="not-used"
        )
        cls.other = get_user_model().objects.create_user(
            username="image-studio-other", password="not-used"
        )

    def setUp(self):
        self.client.force_login(self.owner)
        self.url = reverse("ai_core:image-studio")

    def visit(self, **overrides):
        flags = {
            "VORNEQ_ENV": "staging", "DEBUG": False, "ALLOWED_HOSTS": ["testserver"],
            "VORNEQ_AI_IMAGE_ENABLED": True,
            "VORNEQ_AI_IMAGE_UI_ENABLED": True,
            "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False,
            "VORNEQ_AI_IMAGE_PROVIDER": "mock",
            "VORNEQ_AI_IMAGE_AUTHORIZED_SHA": BASE_SHA,
            "VORNEQ_AI_IMAGE_OWNER_AUTH": "OWNER-AUTH-AI-IMAGE-STAGING-TEST-20261121",
            "VORNEQ_AI_IMAGE_ALLOWED_USER_IDS": str(self.owner.pk),
            "VORNEQ_AI_EMERGENCY_STOP": False,
        }
        flags.update(overrides)
        with override_settings(**flags), patch.dict(os.environ, {
            "RENDER_SERVICE_ID": STAGING_ID, "RENDER_GIT_COMMIT": BASE_SHA,
        }):
            # English copy assertions must not depend on CI/user locale cookies.
            return self.client.get(self.url + "?lang=en")

    def test_staging_allowlisted_mock_actor_can_view_without_starting_a_job(self):
        result = self.visit()
        self.assertEqual(result.status_code, 200)
        self.assertIn("no-store", result["Cache-Control"])
        self.assertEqual(result["X-Robots-Tag"], "noindex, nofollow")
        self.assertContains(result, "Image Studio")
        self.assertContains(result, reverse("ai_core:image-jobs"))
        self.assertContains(result, "data-vq-image-consent")
        self.assertContains(result, "1024x1024")
        self.assertContains(result, "image-studio.js")
        self.assertNotContains(result, "VORNEQ_OPENAI_IMAGE_API_KEY")
        self.assertNotContains(result, "OPENAI_API_KEY")

    def test_ui_default_off_even_if_image_api_is_enabled(self):
        self.assertEqual(self.visit(VORNEQ_AI_IMAGE_UI_ENABLED=False).status_code, 404)

    def test_image_emergency_stop_denies_ui(self):
        self.assertEqual(self.visit(VORNEQ_AI_EMERGENCY_STOP=True).status_code, 404)

    def test_production_never_serves_ui(self):
        self.assertEqual(self.visit(VORNEQ_ENV="production").status_code, 404)

    def test_unlisted_user_cannot_view_ui(self):
        self.client.force_login(self.other)
        self.assertEqual(self.visit().status_code, 404)

    def test_anonymous_when_ui_is_on_gets_no_content(self):
        self.client.logout()
        result = self.visit()
        self.assertEqual(result.status_code, 401)
        self.assertEqual(result["X-Robots-Tag"], "noindex, nofollow")

    def test_wrong_commit_or_service_denied(self):
        self.assertEqual(self.visit(VORNEQ_AI_IMAGE_AUTHORIZED_SHA="f" * 40).status_code, 404)

    def test_paid_provider_must_pass_separate_policy(self):
        with patch("apps.ai_core.image_generation.page.paid_provider_enabled", return_value=False):
            self.assertEqual(self.visit(
                VORNEQ_AI_IMAGE_PROVIDER="openai", VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=True
            ).status_code, 404)
        with patch("apps.ai_core.image_generation.page.paid_provider_enabled", return_value=True):
            response = self.visit(
                VORNEQ_AI_IMAGE_PROVIDER="openai", VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=True
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "may incur an OpenAI charge")

    def test_persian_rtl_and_localized_warning(self):
        with patch("apps.ai_core.image_generation.page.get_language", return_value="en"):
            flags = dict(VORNEQ_ENV="staging", DEBUG=False, ALLOWED_HOSTS=["testserver"],
                         VORNEQ_AI_IMAGE_ENABLED=True, VORNEQ_AI_IMAGE_UI_ENABLED=True,
                         VORNEQ_AI_IMAGE_PROVIDER="mock", VORNEQ_AI_EMERGENCY_STOP=False,
                         VORNEQ_AI_IMAGE_AUTHORIZED_SHA=BASE_SHA,
                         VORNEQ_AI_IMAGE_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-STAGING-TEST-20261121",
                         VORNEQ_AI_IMAGE_ALLOWED_USER_IDS=str(self.owner.pk))
            with override_settings(**flags), patch.dict(os.environ, {
                "RENDER_SERVICE_ID": STAGING_ID, "RENDER_GIT_COMMIT": BASE_SHA,
            }):
                result = self.client.get(self.url + "?lang=fa")
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, 'dir="rtl"')
        self.assertContains(result, "استودیوی تصویر")


class ImageStudioStaticContractTests(SimpleTestCase):
    def test_languages_complete(self):
        expected = set(LABELS["en"])
        for language in ("fa", "de"):
            self.assertEqual(set(LABELS[language]), expected)
            self.assertTrue(all(LABELS[language].values()))

    def test_one_post_no_automatic_retry_and_no_browser_persistence(self):
        self.assertEqual(JS.count('method: "POST"'), 1)
        self.assertEqual(JS.count('method: "GET"'), 1)
        self.assertIn("sentOnce = true", JS)
        self.assertIn("currentId = window.crypto.randomUUID()", JS)
        self.assertIn('"X-CSRFToken": csrf.value', JS)
        self.assertIn('credentials: "same-origin"', JS)
        for forbidden in ("localStorage", "sessionStorage", "innerHTML",
                          "api.openai.com", "setInterval(", "window.location.reload("):
            self.assertNotIn(forbidden, JS)

    def test_signed_link_only_https_and_no_referrer(self):
        self.assertIn('candidate.protocol !== "https:"', JS)
        self.assertIn('referrerpolicy="no-referrer"',
                      (Path(settings.BASE_DIR) / "apps/ai_core/templates/ai_core/image_studio.html"
                       ).read_text(encoding="utf-8"))
        self.assertIn("@media (max-width: 800px)", CSS)

    def test_no_inline_js_or_new_workflows(self):
        tpl = (Path(settings.BASE_DIR) / "apps/ai_core/templates/ai_core/image_studio.html"
               ).read_text(encoding="utf-8")
        self.assertNotIn("onclick=", tpl)
        self.assertNotIn("<script>", tpl)
        self.assertIn('data-vq-image-status', tpl)
        self.assertIn('type="checkbox"', tpl)
