import os
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.content.models import Article
from apps.media.models import MediaAsset
from library.models import LibraryItem
from marketplace.models import Product


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
        with patch.dict(os.environ, {"VORNEQ_ALLOW_STAGING_SEED": "yes"}):
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
