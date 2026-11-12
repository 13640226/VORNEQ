"""Phase C safe chat-preview tests. No model/network access or real credentials."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import override


class ChatPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="phase-c-local-synthetic", password="synthetic-never-reuse")

    def setUp(self):
        self.url = reverse("ai_core:chat")

    def test_off_by_default_fails_closed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    @override_settings(VORNEQ_ENV="production", VORNEQ_AI_PHASE_B_ENABLED=True,
                       VORNEQ_AI_PHASE_C_ENABLED=True)
    def test_prod_guard_even_if_flags_forced(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        home = self.client.get(reverse("home"))
        self.assertEqual(home.status_code, 200)
        self.assertNotContains(home, "data-vq-phase-c-link")

    @override_settings(VORNEQ_ENV="staging", VORNEQ_AI_PHASE_B_ENABLED=True,
                       VORNEQ_AI_PHASE_C_ENABLED=True)
    def test_staging_guard_even_if_flags_forced(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("home")), "data-vq-phase-c-link")

    @override_settings(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=False,
                       VORNEQ_AI_PHASE_C_ENABLED=True)
    def test_phase_b_dependency_guard(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    @override_settings(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=True,
                       VORNEQ_AI_PHASE_C_ENABLED=True)
    def test_anonymous_preview_denied_and_not_linked(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertNotContains(self.client.get(reverse("home")), "data-vq-phase-c-link")

    @override_settings(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=True,
                       VORNEQ_AI_PHASE_C_ENABLED=True)
    def test_development_preview_is_secure_and_links_to_local_api(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url + "?lang=de")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertContains(response, "VORNEQ KI-Chat")
        self.assertContains(response, 'data-vq-language="de"')
        self.assertContains(response, reverse("ai_core:ask-grounded"))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "phase-c-chat")
        self.assertContains(response, "phase-c-chat")
        home = self.client.get(reverse("home"))
        self.assertContains(home, "data-vq-phase-c-link")
        self.assertNotContains(home, "AI answers · coming soon")

    @override_settings(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=True,
                       VORNEQ_AI_PHASE_C_ENABLED=True)
    def test_three_languages_and_rtl_home(self):
        self.client.force_login(self.user)
        for lang, expected in (
            ("fa", "گفت‌وگوی هوش مصنوعی VORNEQ"),
            ("de", "VORNEQ KI-Chat"),
            ("en", "VORNEQ AI chat"),
        ):
            with self.subTest(lang=lang):
                with override(lang):
                    response = self.client.get(self.url + "?lang=" + lang)
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, expected)
                    self.assertContains(response, 'data-vq-language="' + lang + '"')
                    if lang == "fa":
                        self.assertContains(response, 'dir="rtl"')
                    homepage = self.client.get(reverse("home"))
                    self.assertContains(homepage, "data-vq-phase-c-link")
                    if lang == "fa":
                        self.assertContains(homepage, 'dir="rtl"')

    @override_settings(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=True,
                       VORNEQ_AI_PHASE_C_ENABLED=True)
    def test_get_only_and_untrusted_language_fallback(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url).status_code, 405)
        response = self.client.get(self.url + "?lang=../../secret")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-vq-language="../../secret"')
