import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def avatar_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".img"
    return f"avatars/{instance.user_id}/{uuid.uuid4().hex}{suffix}"


class UserProfile(models.Model):
    """Presentation-only profile data for an authenticated user.

    This model deliberately stays separate from core Identity/Reputation so
    changing an avatar or biography never rewrites trust history.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile_data",
    )
    avatar = models.ImageField(upload_to=avatar_upload_to, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"profile:{self.user_id}"
