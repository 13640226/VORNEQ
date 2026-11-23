"""Fail-closed tests for uncapped Production image policy intent."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.ai_core.image_generation.production_preflight import (
    production_image_admission_allowed, production_image_preflight,
)


class ProductionImagePreflightTests(SimpleTestCase):
    def setUp(self):
        self.admin = SimpleNamespace(
            pk=1, is_authenticated=True, is_active=True,
            is_staff=True, is_superuser=True,
        )
        self.flags = {
            "VORNEQ_ENV": "production", "DEBUG": False,
            "VORNEQ_AI_EMERGENCY_STOP": False,
            "VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET": True,
        }

    def inspect(self, user=None, **changes):
        flags = dict(self.flags, **changes)
        with override_settings(**flags), patch.dict(
            "os.environ", {"RENDER_SERVICE_ID": "srv-dadn07eq1p3s73eccau0"}
        ), patch(
            "apps.ai_core.image_generation.production_preflight.production_release_identity",
            return_value=True,
        ):
            actor = self.admin if user is None else user
            report = production_image_preflight(actor)
            self.assertFalse(production_image_admission_allowed(actor))
            return report

    def test_uncapped_policy_does_not_open_paid_route(self):
        report = self.inspect()
        self.assertTrue(report["uncapped_policy_requested"])
        self.assertTrue(report["owner_admin_1"])
        self.assertFalse(report["paid_route_implemented"])
        self.assertFalse(report["production_worker_authorized"])

    def test_other_admin_denied(self):
        other = SimpleNamespace(pk=3, is_authenticated=True, is_active=True,
                                is_staff=True, is_superuser=True)
        self.assertFalse(self.inspect(other)["owner_admin_1"])

    def test_old_financial_caps_not_required_for_policy_intent(self):
        self.assertTrue(self.inspect(
            VORNEQ_AI_IMAGE_PRODUCTION_PROJECT_BUDGET_MICROUSD=None,
            VORNEQ_AI_IMAGE_PRODUCTION_DAILY_CAP_MICROUSD=None,
            VORNEQ_AI_IMAGE_PRODUCTION_MAX_REQUEST_MICROUSD=None,
        )["uncapped_policy_requested"])

    def test_uncapped_switch_must_be_exact_true(self):
        self.assertFalse(self.inspect(
            VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET="true"
        )["uncapped_policy_requested"])
        self.assertFalse(self.inspect(
            VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET=False
        )["uncapped_policy_requested"])

    def test_emergency_stop_denied(self):
        self.assertFalse(self.inspect(
            VORNEQ_AI_EMERGENCY_STOP=True
        )["emergency_stop_clear"])

    def test_debug_denied(self):
        self.assertFalse(self.inspect(DEBUG=True)["debug_disabled"])
