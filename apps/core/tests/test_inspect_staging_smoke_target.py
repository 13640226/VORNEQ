import os
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from marketplace.models import Product


class InspectSmokeTargetTests(TestCase):
    def test_prod_refuses_before_creating_fixture(self):
        with override_settings(VORNEQ_ENV="production"):
            with patch.dict(os.environ, {
                "VORNEQ_ALLOW_INSPECT_STAGING_SMOKE": "yes",
                "VORNEQ_EXPECTED_STAGING_DATABASE": "vorneq_staging_db_test",
            }):
                with self.assertRaisesRegex(CommandError, "outside VORNEQ_ENV"):
                    call_command("inspect_staging_smoke")
        self.assertFalse(Product.objects.exists())

    def test_wrong_database_refuses_before_creating_fixture(self):
        with override_settings(VORNEQ_ENV="staging"):
            with patch.dict(os.environ, {
                "VORNEQ_ALLOW_INSPECT_STAGING_SMOKE": "yes",
                "VORNEQ_EXPECTED_STAGING_DATABASE": "vorneq_staging_db_test",
            }):
                with patch("apps.core.management.commands._staging_target_guard.connection") as target:
                    target.vendor = "postgresql"
                    target.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                        "vorneq_production_db",
                    )
                    with self.assertRaisesRegex(CommandError, "does not match"):
                        call_command("inspect_staging_smoke")
        self.assertFalse(Product.objects.exists())
