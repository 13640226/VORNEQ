from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.core.models import ArtifactIdentityRole, Identity
from apps.core.services.registry import resolve_artifact
from apps.media.models import MediaAsset
from apps.media.services import register_media_asset


class MediaFoundationTests(TestCase):
    def _image(self, **overrides):
        values = {
            "media_type": MediaAsset.MediaType.IMAGE,
            "file": SimpleUploadedFile("image.jpg", b"fake-image", content_type="image/jpeg"),
            "mime_type": "image/jpeg",
            "byte_size": 10,
            "width": 1200,
            "height": 800,
        }
        values.update(overrides)
        return MediaAsset.objects.create(**values)

    def _identity(self, name):
        return Identity.objects.create(kind=Identity.Kind.HUMAN, display_name=name)

    def test_image_requires_intrinsic_dimensions(self):
        asset = MediaAsset(
            media_type=MediaAsset.MediaType.IMAGE,
            file=SimpleUploadedFile("image.jpg", b"x", content_type="image/jpeg"),
            mime_type="image/jpeg",
            byte_size=1,
        )
        with self.assertRaises(ValidationError):
            asset.full_clean()

    def test_image_rejects_non_image_mime_type(self):
        asset = MediaAsset(
            media_type=MediaAsset.MediaType.IMAGE,
            file=SimpleUploadedFile("image.jpg", b"x", content_type="application/octet-stream"),
            mime_type="application/octet-stream",
            byte_size=1,
            width=10,
            height=10,
        )
        with self.assertRaises(ValidationError):
            asset.full_clean()

    def test_registration_creates_artifact_and_creator_role(self):
        asset = self._image()
        creator = self._identity("Creator")

        result = register_media_asset(asset, creator)

        self.assertTrue(result["artifact_created"])
        self.assertTrue(result["creator_role_created"])
        self.assertEqual(resolve_artifact(asset), result["artifact"])
        self.assertEqual(result["creator_role"].role, ArtifactIdentityRole.Role.CREATOR)
        self.assertTrue(result["creator_role"].is_primary)

    def test_registration_can_bind_explicit_publisher(self):
        asset = self._image()
        creator = self._identity("Creator")
        publisher = self._identity("Publisher")

        result = register_media_asset(asset, creator, publisher_identity=publisher)

        self.assertTrue(result["publisher_role_created"])
        self.assertEqual(result["publisher_role"].identity, publisher)
        self.assertEqual(result["publisher_role"].role, ArtifactIdentityRole.Role.PUBLISHER)

    def test_registration_is_idempotent(self):
        asset = self._image()
        creator = self._identity("Creator")

        first = register_media_asset(asset, creator)
        second = register_media_asset(asset, creator)

        self.assertTrue(first["artifact_created"])
        self.assertTrue(first["creator_role_created"])
        self.assertFalse(second["artifact_created"])
        self.assertFalse(second["creator_role_created"])
        self.assertEqual(first["artifact"], second["artifact"])

    def test_registration_rejects_inactive_creator(self):
        asset = self._image()
        creator = self._identity("Inactive Creator")
        creator.is_active = False
        creator.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            register_media_asset(asset, creator)

        self.assertIsNone(resolve_artifact(asset))
