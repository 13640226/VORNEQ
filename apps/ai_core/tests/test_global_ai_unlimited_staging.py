"""Offline tests for the opt-in staging-only quota bypass."""
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from apps.ai_core.global_budget import reserve_global_request
from apps.ai_core.engine.budget import BudgetExceeded


class UnlimitedStagingPolicyTests(SimpleTestCase):
    @override_settings(VORNEQ_ENV="staging", VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=True)
    def test_explicit_staging_opt_in_bypasses_cache(self):
        with patch("apps.ai_core.global_budget.cache") as cache:
            reserve_global_request(1)
            cache.add.assert_not_called()
            cache.incr.assert_not_called()

    @override_settings(VORNEQ_ENV="production", VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=True)
    def test_production_does_not_bypass(self):
        with patch("apps.ai_core.global_budget.cache") as cache:
            cache.incr.return_value = 1
            reserve_global_request(1)
            self.assertEqual(cache.incr.call_count, 3)

    @override_settings(VORNEQ_ENV="development", VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=True)
    def test_development_does_not_bypass(self):
        with patch("apps.ai_core.global_budget.cache") as cache:
            cache.incr.return_value = 1
            reserve_global_request(1)
            self.assertEqual(cache.incr.call_count, 3)

    @override_settings(VORNEQ_ENV="staging", VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=False)
    def test_default_staging_still_uses_quota(self):
        with patch("apps.ai_core.global_budget.cache") as cache:
            cache.incr.return_value = 1
            reserve_global_request(1)
            self.assertEqual(cache.incr.call_count, 3)

    @override_settings(VORNEQ_ENV="staging", VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=True)
    def test_invalid_actor_still_rejected(self):
        with self.assertRaises(BudgetExceeded):
            reserve_global_request(0)
