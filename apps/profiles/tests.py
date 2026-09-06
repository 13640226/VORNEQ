from io import BytesIO
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.core.models import Identity, UserIdentity

from .models import UserProfile


User = get_user_model()


def make_png(name="avatar.png", size=(64, 64)):
    buffer = BytesIO()
    Image.new("RGB", size, color=(30, 90, 180)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class EditableProfileTest(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.user = User.objects.create_user(
            username="profile-user",
            email="profile@example.com",
            password="testpass123",
        )

    def tearDown(self):
        self.settings_override.disable()
        self.media_dir.cleanup()

    def test_edit_requires_authentication(self):
        response = self.client.get(reverse("profile_edit"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_edit_updates_user_and_presentation_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "bio": "Computing and verification.",
                "website": "https://example.com/ada",
            },
        )
        self.assertRedirects(response, reverse("profile"))

        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(self.user.first_name, "Ada")
        self.assertEqual(self.user.last_name, "Lovelace")
        self.assertEqual(profile.bio, "Computing and verification.")
        self.assertEqual(profile.website, "https://example.com/ada")

    def test_avatar_upload_and_private_delivery(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Ada",
                "last_name": "",
                "bio": "",
                "website": "",
                "avatar": make_png(),
            },
        )
        self.assertRedirects(response, reverse("profile"))

        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.avatar.name.startswith(f"avatars/{self.user.id}/"))

        avatar_response = self.client.get(reverse("profile_avatar"))
        self.assertEqual(avatar_response.status_code, 200)
        self.assertEqual(avatar_response["Content-Type"], "image/png")
        self.assertIn("private", avatar_response["Cache-Control"])

    def test_avatar_rejects_non_image_upload(self):
        self.client.force_login(self.user)
        bad_file = SimpleUploadedFile("avatar.png", b"not-an-image", content_type="image/png")
        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "",
                "last_name": "",
                "bio": "",
                "website": "",
                "avatar": bad_file,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a valid image")

    def test_profile_edit_does_not_change_trust_identity(self):
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Canonical Name",
        )
        UserIdentity.objects.create(user=self.user, identity=identity)

        self.client.force_login(self.user)
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Public",
                "last_name": "Name",
                "bio": "Presentation data only.",
                "website": "",
            },
        )

        identity.refresh_from_db()
        self.assertEqual(identity.display_name, "Canonical Name")
        self.assertEqual(UserIdentity.objects.filter(user=self.user).count(), 1)

    def test_remove_avatar(self):
        profile = UserProfile.objects.create(user=self.user, avatar=make_png())
        old_name = profile.avatar.name
        storage = profile.avatar.storage
        self.assertTrue(storage.exists(old_name))

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "",
                "last_name": "",
                "bio": "",
                "website": "",
                "remove_avatar": "on",
            },
        )
        self.assertRedirects(response, reverse("profile"))

        profile.refresh_from_db()
        self.assertFalse(profile.avatar)
        self.assertFalse(storage.exists(old_name))
