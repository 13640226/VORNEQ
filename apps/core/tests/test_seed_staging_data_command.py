import os
from io import StringIO
from contextlib import contextmanager
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.content.models import Article
from apps.media.models import MediaAsset
from library.models import LibraryItem
from marketplace.models import Product


@contextmanager
def permitted_staging_target():
    # This mocks only the command's identity probe; business ORM uses the
    # isolated Django test database, never a live Postgres instance.
    env = {
        "VORNEQ_ALLOW_STAGING_SEED": "yes",
        "VORNEQ_EXPECTED_STAGING_DATABASE": "vorneq_staging_db_test",
        "VORNEQ_EXPECTED_STAGING_DB_USER": "vorneq_staging_db_test_user",
        "VORNEQ_EXPECTED_STAGING_DB_HOST": "staging-db.internal",
        "VORNEQ_EXPECTED_STAGING_DB_PORT": "5432",
    }
    with override_settings(VORNEQ_ENV="staging"):
        with patch.dict(os.environ, env):
            with patch("apps.core.management.commands._staging_target_guard.connection") as target:
                target.vendor = "postgresql"
                target.settings_dict = {"HOST": "staging-db.internal", "PORT": "5432"}
                target.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                    "vorneq_staging_db_test", "vorneq_staging_db_test_user", 5432,
                )
                yield target



class SeedStagingDataCommandTests(TestCase):
    def test_dry_run_does_not_write(self):
        output = StringIO()
        call_command("seed_staging_data", "--count", "2", "--dry-run", stdout=output)

        self.assertEqual(Article.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(LibraryItem.objects.count(), 0)
        self.assertEqual(MediaAsset.objects.count(), 0)
        self.assertIn("Dry run only", output.getvalue())

    def test_force_requires_explicit_environment_guard(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VORNEQ_ALLOW_STAGING_SEED", None)
            with self.assertRaises(CommandError):
                call_command("seed_staging_data", "--count", "1", "--force")

    def test_force_seeds_searchable_public_records(self):
        output = StringIO()
        with permitted_staging_target():
            call_command("seed_staging_data", "--count", "2", "--force", stdout=output)

        self.assertEqual(Article.objects.filter(is_published=True).count(), 2)
        self.assertEqual(
            Product.objects.filter(status=Product.STATUS_APPROVED, is_published=True).count(),
            2,
        )
        self.assertEqual(LibraryItem.objects.filter(is_published=True).count(), 2)
        self.assertEqual(MediaAsset.objects.filter(is_active=True).count(), 2)
        self.assertTrue(Article.objects.filter(title__icontains="ai").exists())
        self.assertTrue(Product.objects.filter(title__icontains="knowledge").exists())
        self.assertIn("Staging benchmark seed complete", output.getvalue())

    def test_force_rejects_production_even_when_opted_in(self):
        with override_settings(VORNEQ_ENV="production"):
            with patch.dict(os.environ, {
                "VORNEQ_ALLOW_STAGING_SEED": "yes",
                "VORNEQ_EXPECTED_STAGING_DATABASE": "vorneq_staging_db_test",
            }):
                with self.assertRaisesRegex(CommandError, "outside VORNEQ_ENV"):
                    call_command("seed_staging_data", "--count", "1", "--force")
        self.assertEqual(Product.objects.count(), 0)

    def test_force_rejects_missing_target_identity(self):
        with override_settings(VORNEQ_ENV="staging"):
            with patch.dict(os.environ, {
                "VORNEQ_ALLOW_STAGING_SEED": "yes",
                "VORNEQ_EXPECTED_STAGING_DATABASE": "",
            }):
                with self.assertRaisesRegex(CommandError, "staging database identity"):
                    call_command("seed_staging_data", "--count", "1", "--force")
        self.assertEqual(Product.objects.count(), 0)

    def test_force_rejects_wrong_database_identity(self):
        with permitted_staging_target() as target:
            target.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                "vorneq_production_db", "vorneq_staging_db_test_user", 5432,
            )
            with self.assertRaisesRegex(CommandError, "does not match"):
                call_command("seed_staging_data", "--count", "1", "--force")
        self.assertEqual(Product.objects.count(), 0)

    def test_force_rejects_non_postgres_target(self):
        with permitted_staging_target() as target:
            target.vendor = "sqlite"
            with self.assertRaisesRegex(CommandError, "must be PostgreSQL"):
                call_command("seed_staging_data", "--count", "1", "--force")
        self.assertEqual(Product.objects.count(), 0)

    def test_force_rejects_wrong_postgres_login_role(self):
        with permitted_staging_target() as target:
            target.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                "vorneq_staging_db_test", "vorneq_production_db_user", 5432,
            )
            with self.assertRaisesRegex(CommandError, "runtime identity"):
                call_command("seed_staging_data", "--count", "1", "--force")
        self.assertEqual(Product.objects.count(), 0)

    def test_force_rejects_wrong_endpoint(self):
        with permitted_staging_target() as target:
            target.settings_dict = {"HOST": "production-db.internal", "PORT": "5432"}
            with self.assertRaisesRegex(CommandError, "connection endpoint"):
                call_command("seed_staging_data", "--count", "1", "--force")
        self.assertEqual(Product.objects.count(), 0)

    def test_force_rejects_wrong_server_port(self):
        with permitted_staging_target() as target:
            target.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                "vorneq_staging_db_test", "vorneq_staging_db_test_user", 6432,
            )
            with self.assertRaisesRegex(CommandError, "runtime identity"):
                call_command("seed_staging_data", "--count", "1", "--force")
        self.assertEqual(Product.objects.count(), 0)
