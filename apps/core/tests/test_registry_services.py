from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from apps.core.models import (
    Artifact,
    ArtifactBinding,
    ArtifactIdentityRole,
    Identity,
    UserIdentity,
)
from apps.core.services.registry import (
    register_artifact,
    register_user_identity,
    resolve_artifact,
    resolve_identity_for_user,
)
from marketplace.models import Product


User = get_user_model()


class RegistryServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="registry-user", password="pass12345")
        self.product = Product.objects.create(
            seller=self.user,
            title="Registry Product",
        )

    def test_register_artifact_is_idempotent_and_resolvable(self):
        artifact1, created1 = register_artifact(self.product)
        artifact2, created2 = register_artifact(self.product)

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(artifact1, artifact2)
        self.assertEqual(resolve_artifact(self.product), artifact1)
        self.assertEqual(Artifact.objects.count(), 1)
        self.assertEqual(ArtifactBinding.objects.count(), 1)
        self.assertEqual(artifact1.kind, Artifact.Kind.PRODUCT)

    def test_registration_does_not_infer_seller_role(self):
        register_artifact(self.product)
        self.assertFalse(ArtifactIdentityRole.objects.exists())

    def test_resolve_unregistered_artifact_returns_none(self):
        self.assertIsNone(resolve_artifact(self.product))

    def test_user_is_not_a_supported_artifact_target(self):
        with self.assertRaises(ValidationError):
            register_artifact(self.user)

    def test_register_user_identity_is_idempotent_and_human(self):
        identity1, created1 = register_user_identity(self.user)
        identity2, created2 = register_user_identity(self.user)

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(identity1, identity2)
        self.assertEqual(identity1.kind, Identity.Kind.HUMAN)
        self.assertEqual(resolve_identity_for_user(self.user), identity1)
        self.assertEqual(Identity.objects.count(), 1)
        self.assertEqual(UserIdentity.objects.count(), 1)

    def test_backfill_command_is_idempotent(self):
        out1 = StringIO()
        call_command("backfill_registry", stdout=out1)
        self.assertEqual(Artifact.objects.count(), 1)
        self.assertEqual(ArtifactBinding.objects.count(), 1)
        self.assertEqual(Identity.objects.count(), 1)
        self.assertEqual(UserIdentity.objects.count(), 1)

        out2 = StringIO()
        call_command("backfill_registry", stdout=out2)
        self.assertEqual(Artifact.objects.count(), 1)
        self.assertEqual(ArtifactBinding.objects.count(), 1)
        self.assertEqual(Identity.objects.count(), 1)
        self.assertEqual(UserIdentity.objects.count(), 1)
        self.assertIn("1 existing", out2.getvalue())

    def test_backfill_dry_run_rolls_back(self):
        out = StringIO()
        call_command("backfill_registry", "--dry-run", stdout=out)

        self.assertEqual(Artifact.objects.count(), 0)
        self.assertEqual(ArtifactBinding.objects.count(), 0)
        self.assertEqual(Identity.objects.count(), 0)
        self.assertEqual(UserIdentity.objects.count(), 0)
        self.assertIn("DRY RUN", out.getvalue())
