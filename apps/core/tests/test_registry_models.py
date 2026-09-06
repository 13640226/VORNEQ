from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.core.models import (
    Artifact,
    ArtifactBinding,
    ArtifactIdentityRole,
    Identity,
    UserIdentity,
)
from marketplace.models import Product


User = get_user_model()


class RegistryModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="registry-user", password="testpass")
        self.identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Registry User",
        )
        self.artifact = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        self.product = Product.objects.create(
            seller=self.user,
            title="Registry Product",
        )

    def test_registry_ids_are_uuid_and_independent_from_vertical_pk(self):
        self.assertNotEqual(str(self.artifact.id), str(self.product.pk))
        self.assertEqual(len(str(self.artifact.id)), 36)

    def test_artifact_binding_accepts_supported_product_with_string_object_id(self):
        binding = ArtifactBinding(
            artifact=self.artifact,
            content_type=ContentType.objects.get_for_model(Product),
            object_id=str(self.product.pk),
            created_by=self.user,
        )
        binding.full_clean()
        binding.save()
        self.assertEqual(binding.content_object, self.product)

    def test_artifact_binding_rejects_unsupported_model(self):
        binding = ArtifactBinding(
            artifact=self.artifact,
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(self.user.pk),
        )
        with self.assertRaises(ValidationError):
            binding.full_clean()

    def test_artifact_binding_rejects_missing_target(self):
        binding = ArtifactBinding(
            artifact=self.artifact,
            content_type=ContentType.objects.get_for_model(Product),
            object_id="999999999",
        )
        with self.assertRaises(ValidationError):
            binding.full_clean()

    def test_vertical_object_can_only_have_one_artifact_binding(self):
        content_type = ContentType.objects.get_for_model(Product)
        ArtifactBinding.objects.create(
            artifact=self.artifact,
            content_type=content_type,
            object_id=str(self.product.pk),
        )
        second_artifact = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ArtifactBinding.objects.create(
                    artifact=second_artifact,
                    content_type=content_type,
                    object_id=str(self.product.pk),
                )

    def test_user_identity_requires_human_identity(self):
        agent = Identity.objects.create(
            kind=Identity.Kind.AGENT,
            display_name="Test Agent",
        )
        binding = UserIdentity(user=self.user, identity=agent)
        with self.assertRaises(ValidationError):
            binding.full_clean()

    def test_user_and_identity_bindings_are_one_to_one(self):
        UserIdentity.objects.create(user=self.user, identity=self.identity)
        another_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Another Identity",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserIdentity.objects.create(user=self.user, identity=another_identity)

    def test_artifact_identity_role_is_unique_per_role(self):
        ArtifactIdentityRole.objects.create(
            artifact=self.artifact,
            identity=self.identity,
            role=ArtifactIdentityRole.Role.SELLER,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ArtifactIdentityRole.objects.create(
                    artifact=self.artifact,
                    identity=self.identity,
                    role=ArtifactIdentityRole.Role.SELLER,
                )

    def test_role_validity_window_must_be_ordered(self):
        now = timezone.now()
        role = ArtifactIdentityRole(
            artifact=self.artifact,
            identity=self.identity,
            role=ArtifactIdentityRole.Role.AUTHOR,
            valid_from=now,
            valid_until=now,
        )
        with self.assertRaises(ValidationError):
            role.full_clean()

    def test_library_author_strings_are_not_inferred(self):
        # Foundation models expose no string-matching or automatic identity creation path.
        self.assertFalse(hasattr(ArtifactBinding, "author"))
        self.assertFalse(hasattr(UserIdentity, "display_name"))
