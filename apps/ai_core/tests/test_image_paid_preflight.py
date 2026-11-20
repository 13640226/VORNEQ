"""The paid image preflight never turns feature flags on or authorizes spend."""
import json
import os
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.ai_core.management.commands.inspect_image_paid_preflight import (
    collect_image_paid_preflight,
)


class ImagePaidPreflightTest(SimpleTestCase):
    @override_settings(VORNEQ_ENV="production", DEBUG=False)
    def test_production_never_queries_databases_or_claims_authorization(self):
        with patch(
            "apps.ai_core.management.commands.inspect_image_paid_preflight._check_staging_db",
            side_effect=AssertionError("must not query production"),
        ), patch(
            "apps.ai_core.management.commands.inspect_image_paid_preflight._check_image_ledger",
            side_effect=AssertionError("must not query production"),
        ):
            report = collect_image_paid_preflight()
        self.assertEqual(report["authorization"], "NO_GO")
        self.assertEqual(report["db_result"], "staging_identity_required")

    @override_settings(
        VORNEQ_ENV="staging", DEBUG=False,
        VORNEQ_AI_IMAGE_ENABLED=False,
        VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=False,
        VORNEQ_AI_IMAGE_PROVIDER="mock",
        VORNEQ_AI_IMAGE_AUTHORIZED_SHA="",
        VORNEQ_AI_IMAGE_OWNER_AUTH="",
        VORNEQ_AI_IMAGE_ALLOWED_USER_IDS="",
        VORNEQ_AI_IMAGE_LEDGER_ID="",
    )
    def test_staging_reports_missing_dependencies_without_activation(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": "srv-dbm7dvc9v7es7393g70g"}):
            with patch(
                "apps.ai_core.management.commands.inspect_image_paid_preflight._check_staging_db",
                return_value=(True, False, "ok"),
            ), patch(
                "apps.ai_core.management.commands.inspect_image_paid_preflight._check_image_ledger",
                return_value=(False, False, False, "image_ledger_not_configured"),
            ):
                report = collect_image_paid_preflight()
        self.assertEqual(report["authorization"], "NO_GO")
        self.assertFalse(report["checks"]["image_migration_0004_applied"])
        self.assertFalse(report["checks"]["paid_calls_currently_enabled"])
        self.assertEqual(report["ledger_result"], "image_ledger_not_configured")
        dumped = json.dumps(report)
        self.assertNotIn("secret_access_key", dumped)
        self.assertNotIn("api_key_value", dumped)
