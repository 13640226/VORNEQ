"""G-02: the development AI path must stay closed on hosted runtimes (Render).

No network, no provider, no real key. Settings are resolved in a fresh
interpreter so the module-level flag computation itself is exercised.
"""
import json
import os
import subprocess
import sys
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

PROD_SERVICE = "srv-dadn07eq1p3s73eccau0"
ALL_FLAGS = {
    "VORNEQ_AI_CORE_ENABLED": "true", "VORNEQ_AI_PHASE_B_ENABLED": "true",
    "VORNEQ_AI_PHASE_C_ENABLED": "true", "VORNEQ_AI_STAGING_TRIAL_ENABLED": "true",
}


def resolve(extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("VORNEQ_", "RENDER", "OPENAI_", "DATABASE_URL", "REDIS_URL"))}
    env.update({"DJANGO_SECRET_KEY": "x" * 60, "DJANGO_DEBUG": "false",
                "DJANGO_ALLOWED_HOSTS": "localhost", "DJANGO_SETTINGS_MODULE": "config.settings"})
    env.update(ALL_FLAGS)
    env.update(extra)
    code = ("import django,json;django.setup();from django.conf import settings as s;"
            "print(json.dumps([s.VORNEQ_AI_CORE_ENABLED,s.VORNEQ_AI_PHASE_B_ENABLED,"
            "s.VORNEQ_AI_PHASE_C_ENABLED,s.VORNEQ_AI_STAGING_TRIAL_ENABLED]))")
    out = subprocess.run([sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env,
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise AssertionError(out.stderr[-2000:])
    return json.loads(out.stdout.strip().splitlines()[-1])


class HostedRuntimeSettingsTests(SimpleTestCase):
    def test_local_development_unchanged(self):
        self.assertEqual(resolve({"VORNEQ_ENV": "development"}), [True, True, True, False])

    def test_development_label_with_render_marker_is_closed(self):
        self.assertEqual(resolve({"VORNEQ_ENV": "development", "RENDER": "true"}),
                         [False, False, False, False])

    def test_development_label_with_render_service_id_is_closed(self):
        self.assertEqual(resolve({"VORNEQ_ENV": "development", "RENDER_SERVICE_ID": PROD_SERVICE}),
                         [False, False, False, False])

    def test_staging_trial_path_unchanged_on_render(self):
        self.assertEqual(resolve({"VORNEQ_ENV": "staging", "RENDER": "true",
                                  "RENDER_SERVICE_ID": "srv-dbm7dvc9v7es7393g70g"}),
                         [True, True, False, True])

    def test_production_still_closed(self):
        self.assertEqual(resolve({"VORNEQ_ENV": "production", "RENDER": "true"}),
                         [False, False, False, False])


@override_settings(VORNEQ_ENV="development", VORNEQ_AI_CORE_ENABLED=True,
                   VORNEQ_AI_PHASE_B_ENABLED=True, VORNEQ_AI_PHASE_C_ENABLED=True)
class HostedRuntimeViewGuardTests(TestCase):
    """Defense in depth: even with forced flags, views refuse on a hosted runtime."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="g02-user", email="g02@example.invalid", password="synthetic-only")

    def setUp(self):
        self.client.force_login(self.user)

    def post(self, name):
        return self.client.post(reverse(name), data=json.dumps({"question": "public sample", "language": "en"}),
                                content_type="application/json")

    def test_endpoints_404_on_render_and_provider_never_constructed(self):
        with patch.dict(os.environ, {"RENDER": "true"}), \
                patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider") as provider, \
                patch("apps.ai_core.views.ask_public") as offline:
            self.assertEqual(self.post("ai_core:ask-grounded").status_code, 404)
            self.assertEqual(self.post("ai_core:ask").status_code, 404)
            self.assertEqual(self.client.get(reverse("ai_core:chat")).status_code, 404)
        provider.assert_not_called()
        offline.assert_not_called()

    def test_local_development_still_reaches_endpoint(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("RENDER")}
        with patch.dict(os.environ, env, clear=True), \
                patch("apps.ai_core.views.ask_public",
                      return_value={"mode": "sources_only", "citations": []}) as offline:
            self.assertEqual(self.post("ai_core:ask").status_code, 200)
        offline.assert_called_once()
