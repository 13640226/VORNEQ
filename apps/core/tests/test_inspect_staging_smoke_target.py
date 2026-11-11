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
                "VORNEQ_EXPECTED_STAGING_DB_USER": "vorneq_staging_db_test_user",
                "VORNEQ_EXPECTED_STAGING_DB_HOST": "staging-db.internal",
                "VORNEQ_EXPECTED_STAGING_DB_PORT": "5432",
            }):
                with self.assertRaisesRegex(CommandError, "outside VORNEQ_ENV"):
                    call_command("inspect_staging_smoke")
        self.assertFalse(Product.objects.exists())

    def test_wrong_database_refuses_before_creating_fixture(self):
        with override_settings(VORNEQ_ENV="staging"):
            with patch.dict(os.environ, {
                "VORNEQ_ALLOW_INSPECT_STAGING_SMOKE": "yes",
                "VORNEQ_EXPECTED_STAGING_DATABASE": "vorneq_staging_db_test",
                "VORNEQ_EXPECTED_STAGING_DB_USER": "vorneq_staging_db_test_user",
                "VORNEQ_EXPECTED_STAGING_DB_HOST": "staging-db.internal",
                "VORNEQ_EXPECTED_STAGING_DB_PORT": "5432",
            }):
                with patch("apps.core.management.commands._staging_target_guard.connection") as target:
                    target.vendor = "postgresql"
                    target.settings_dict = {"HOST": "staging-db.internal", "PORT": "5432"}
                    target.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                        "vorneq_production_db", "vorneq_staging_db_test_user", 5432,
                    )
                    with self.assertRaisesRegex(CommandError, "runtime identity"):
                        call_command("inspect_staging_smoke")
        self.assertFalse(Product.objects.exists())

    def test_wrong_endpoint_refuses_before_creating_fixture(self):
        with override_settings(VORNEQ_ENV="staging"):
            with patch.dict(os.environ, {
                "VORNEQ_ALLOW_INSPECT_STAGING_SMOKE": "yes",
                "VORNEQ_EXPECTED_STAGING_DATABASE": "vorneq_staging_db_test",
                "VORNEQ_EXPECTED_STAGING_DB_USER": "vorneq_staging_db_test_user",
                "VORNEQ_EXPECTED_STAGING_DB_HOST": "staging-db.internal",
                "VORNEQ_EXPECTED_STAGING_DB_PORT": "5432",
            }):
                with patch("apps.core.management.commands._staging_target_guard.connection") as target:
                    target.vendor = "postgresql"
                    target.settings_dict = {"HOST": "production-db.internal", "PORT": "5432"}
                    with self.assertRaisesRegex(CommandError, "connection endpoint"):
                        call_command("inspect_staging_smoke")
        self.assertFalse(Product.objects.exists())
