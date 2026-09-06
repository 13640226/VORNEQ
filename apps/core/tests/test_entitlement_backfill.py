from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.core.models import Artifact, Entitlement, Identity
from apps.core.services.entitlement import grant_entitlement
from apps.core.services.registry import register_artifact, register_user_identity
from marketplace.models import Product


User = get_user_model()


class EntitlementBackfillCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="backfill-user",
            password="pass12345",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Backfill Product",
        )

    def _legacy_entitlement_then_bindings(self):
        entitlement = grant_entitlement(self.user, self.product)
        self.assertIsNone(entitlement.identity_id)
        self.assertIsNone(entitlement.artifact_id)
        identity, _ = register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)
        return entitlement, identity, artifact

    def test_force_backfills_existing_legacy_row(self):
        entitlement, identity, artifact = self._legacy_entitlement_then_bindings()
        out = StringIO()

        call_command("backfill_entitlements", force=True, stdout=out)

        entitlement.refresh_from_db()
        self.assertEqual(entitlement.identity, identity)
        self.assertEqual(entitlement.artifact, artifact)
        self.assertIn("updated=1", out.getvalue())
        self.assertIn("conflicts=0", out.getvalue())

    def test_dry_run_reports_but_does_not_persist(self):
        entitlement, _, _ = self._legacy_entitlement_then_bindings()
        out = StringIO()

        call_command("backfill_entitlements", dry_run=True, stdout=out)

        entitlement.refresh_from_db()
        self.assertIsNone(entitlement.identity_id)
        self.assertIsNone(entitlement.artifact_id)
        self.assertIn("DRY RUN", out.getvalue())
        self.assertIn("updated=1", out.getvalue())

    def test_missing_bindings_are_unresolved_and_never_created(self):
        entitlement = grant_entitlement(self.user, self.product)
        out = StringIO()

        call_command("backfill_entitlements", force=True, stdout=out)

        entitlement.refresh_from_db()
        self.assertIsNone(entitlement.identity_id)
        self.assertIsNone(entitlement.artifact_id)
        self.assertEqual(Identity.objects.count(), 0)
        self.assertEqual(Artifact.objects.count(), 0)
        self.assertIn("unresolved=1", out.getvalue())

    def test_existing_matching_canonical_pair_is_idempotent(self):
        identity, _ = register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)
        self.assertEqual(entitlement.identity, identity)
        self.assertEqual(entitlement.artifact, artifact)
        out = StringIO()

        call_command("backfill_entitlements", force=True, stdout=out)

        entitlement.refresh_from_db()
        self.assertEqual(entitlement.identity, identity)
        self.assertEqual(entitlement.artifact, artifact)
        self.assertIn("updated=0", out.getvalue())
        self.assertIn("already_canonical=1", out.getvalue())

    def test_conflicting_canonical_pair_is_reported_without_overwrite(self):
        expected_identity, _ = register_user_identity(self.user)
        expected_artifact, _ = register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)
        wrong_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Wrong backfill identity",
        )
        wrong_artifact = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        Entitlement.objects.filter(pk=entitlement.pk).update(
            identity=wrong_identity,
            artifact=wrong_artifact,
        )
        out = StringIO()

        call_command("backfill_entitlements", force=True, stdout=out)

        entitlement.refresh_from_db()
        self.assertEqual(entitlement.identity, wrong_identity)
        self.assertEqual(entitlement.artifact, wrong_artifact)
        self.assertNotEqual(entitlement.identity, expected_identity)
        self.assertNotEqual(entitlement.artifact, expected_artifact)
        self.assertIn("conflicts=1", out.getvalue())
        self.assertIn("updated=0", out.getvalue())

    def test_command_requires_exactly_one_execution_mode(self):
        with self.assertRaises(CommandError):
            call_command("backfill_entitlements")
        with self.assertRaises(CommandError):
            call_command("backfill_entitlements", dry_run=True, force=True)

    def test_limit_bounds_processed_rows(self):
        entitlement, _, _ = self._legacy_entitlement_then_bindings()
        second_user = User.objects.create_user(username="backfill-user-2")
        second_product = Product.objects.create(
            seller=second_user,
            title="Backfill Product 2",
        )
        grant_entitlement(second_user, second_product)
        register_user_identity(second_user)
        register_artifact(second_product)
        out = StringIO()

        call_command("backfill_entitlements", force=True, limit=1, stdout=out)

        entitlement.refresh_from_db()
        self.assertIsNotNone(entitlement.identity_id)
        self.assertIsNotNone(entitlement.artifact_id)
        self.assertIn("processed=1", out.getvalue())
