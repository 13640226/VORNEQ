import os
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from apps.ai_core.image_generation.policy import production_uncapped_budget_requested, production_enabled

class UncappedProductionIntentTests(SimpleTestCase):
    @override_settings(VORNEQ_ENV="production", VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET=True,
                       VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=True, VORNEQ_AI_EMERGENCY_STOP=False)
    @patch("apps.ai_core.image_generation.policy.production_release_identity", return_value=True)
    def test_intent_does_not_open_paid_route(self, identity):
        self.assertTrue(production_uncapped_budget_requested())
        self.assertFalse(production_enabled())

    @override_settings(VORNEQ_ENV="staging", VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET=True,
                       VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=True, VORNEQ_AI_EMERGENCY_STOP=False)
    @patch("apps.ai_core.image_generation.policy.production_release_identity", return_value=True)
    def test_staging_isolation(self, identity):
        self.assertFalse(production_uncapped_budget_requested())

    @override_settings(VORNEQ_ENV="production", VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET=True,
                       VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=True, VORNEQ_AI_EMERGENCY_STOP=True)
    @patch("apps.ai_core.image_generation.policy.production_release_identity", return_value=True)
    def test_emergency_stop(self, identity):
        self.assertFalse(production_uncapped_budget_requested())

    @override_settings(VORNEQ_ENV="production", VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET=True,
                       VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=True, VORNEQ_AI_EMERGENCY_STOP=False)
    @patch("apps.ai_core.image_generation.policy.production_release_identity", return_value=False)
    def test_missing_deployment_proof(self, identity):
        self.assertFalse(production_uncapped_budget_requested())
