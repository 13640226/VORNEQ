from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.core.management.commands.entitlement_parity_report import (
    _authorization_allowed,
    _canonical_state,
)
from apps.core.models import Artifact, Entitlement, Identity
from apps.core.services.entitlement import grant_entitlement, has_valid_entitlement
from apps.core.services.registry import register_artifact, register_user_identity
from marketplace.models import Product


User = get_user_model()


class EntitlementParityReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="parity-user",
            password="pass12345",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Parity Product",
        )

    def _run_report(self, **options):
        out = StringIO()
        call_command("entitlement_parity_report", stdout=out, **options)
        return out.getvalue()

    def test_reports_legacy_only_without_mutating_row(self):
        entitlement = grant_entitlement(self.user, self.product)
        register_user_identity(self.user)
        register_artifact(self.product)

        output = self._run_report()

        entitlement.refresh_from_db()
        self.assertIsNone(entitlement.identity_id)
        self.assertIsNone(entitlement.artifact_id)
        self.assertIn("legacy_only=1", output)
        self.assertIn("registry_resolved=1", output)
        self.assertIn("authorization_allowed=1", output)

    def test_reports_matching_canonical_pair(self):
        identity, _ = register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)

        output = self._run_report()

        self.assertEqual(entitlement.identity, identity)
        self.assertEqual(entitlement.artifact, artifact)
        self.assertIn("canonical_complete=1", output)
        self.assertIn("canonical_match=1", output)
        self.assertIn("canonical_mismatch=0", output)
        self.assertIn("conflicts=0", output)
        self.assertIn("authorization_allowed=1", output)

    def test_reports_canonical_mismatch_as_conflict_and_denied(self):
        register_user_identity(self.user)
        register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)
        wrong_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Wrong parity identity",
        )
        wrong_artifact = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        Entitlement.objects.filter(pk=entitlement.pk).update(
            identity=wrong_identity,
            artifact=wrong_artifact,
        )

        output = self._run_report(verbose=True)

        self.assertIn("canonical_mismatch=1", output)
        self.assertIn("conflicts=1", output)
        self.assertIn("authorization_denied=1", output)
        self.assertIn("canonical=mismatch", output)
        self.assertFalse(has_valid_entitlement(self.user, self.product))

    def test_registry_unresolved_is_reported_separately(self):
        grant_entitlement(self.user, self.product)

        output = self._run_report()

        self.assertIn("legacy_only=1", output)
        self.assertIn("registry_unresolved=1", output)
        self.assertIn("conflicts=0", output)
        self.assertIn("authorization_allowed=1", output)

    def test_partial_canonical_state_is_classified_defensively(self):
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Unsaved partial identity",
        )
        entitlement = Entitlement(
            user=self.user,
            product=self.product,
            identity=identity,
            artifact=None,
        )

        self.assertEqual(_canonical_state(entitlement), "partial_canonical")
        self.assertFalse(_authorization_allowed(entitlement, identity.pk, None))

    def test_report_authorization_classifier_matches_service(self):
        identity, _ = register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)

        classified = _authorization_allowed(entitlement, identity.pk, artifact.pk)

        self.assertEqual(classified, has_valid_entitlement(self.user, self.product))

    def test_limit_is_deterministic_and_must_be_positive(self):
        grant_entitlement(self.user, self.product)
        second_user = User.objects.create_user(username="parity-user-2")
        second_product = Product.objects.create(
            seller=second_user,
            title="Parity Product 2",
        )
        grant_entitlement(second_user, second_product)

        output = self._run_report(limit=1)
        self.assertIn("processed=1", output)

        with self.assertRaises(CommandError):
            self._run_report(limit=0)
        with self.assertRaises(CommandError):
            self._run_report(limit=-1)
