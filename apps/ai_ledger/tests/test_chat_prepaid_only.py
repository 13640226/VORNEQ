import os
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from apps.ai_ledger import service


@override_settings(VORNEQ_ENV="staging", VORNEQ_AI_EMERGENCY_STOP=False,
                   VORNEQ_AI_CHAT_STAGING_PREPAID_ONLY=True)
class PrepaidOnlyTests(SimpleTestCase):
    def test_no_daily_ceiling_but_reservation_remains(self):
        with patch("apps.ai_core.staging_policy.trial_enabled", return_value=True), \
             patch.object(service, "ledger_configuration", return_value=object()), \
             patch.object(service, "reserve_with_config") as reserve, \
             patch.dict(os.environ, {"RENDER_SERVICE_ID": service.EXPECTED_SERVICES["staging"], "RENDER_GIT_COMMIT": "a"*40}):
            service.reserve(actor_id=3, model="test", input_bytes=100, max_output_tokens=200)
            self.assertIsNone(reserve.call_args.kwargs["staging_daily"])
            self.assertEqual(reserve.call_args.kwargs["environment"], "staging")

    def test_unauthorized_trial_refused(self):
        with patch("apps.ai_core.staging_policy.trial_enabled", return_value=False), patch.object(service, "reserve_with_config") as reserve:
            with self.assertRaises(service.LedgerUnavailable):
                service.reserve(actor_id=3, model="test", input_bytes=100, max_output_tokens=200)
            reserve.assert_not_called()
