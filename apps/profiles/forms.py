from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from .models import UserProfile


MAX_AVATAR_BYTES = 2 * 1024 * 1024
MAX_AVATAR_DIMENSION = 4096
ALLOWED_AVATAR_FORMATS = {"JPEG", "PNG", "WEBP"}


class ProfileEditForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    bio = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    website = forms.URLField(required=False)
    avatar = forms.ImageField(required=False)
    remove_avatar = forms.BooleanField(required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        self.profile, _ = UserProfile.objects.get_or_create(user=user)
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("first_name", user.first_name)
        initial.setdefault("last_name", user.last_name)
        initial.setdefault("bio", self.profile.bio)
        initial.setdefault("website", self.profile.website)
        super().__init__(*args, **kwargs)

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar:
            return avatar

        if avatar.size > MAX_AVATAR_BYTES:
            raise ValidationError("Avatar must be 2 MB or smaller.")

        try:
            position = avatar.tell()
            image = Image.open(avatar)
            image.verify()
            avatar.seek(position)
            image = Image.open(avatar)
            width, height = image.size
            image_format = image.format
            avatar.seek(position)
        except (UnidentifiedImageError, OSError, ValueError):
            raise ValidationError("Upload a valid JPG, PNG, or WebP image.")

        if image_format not in ALLOWED_AVATAR_FORMATS:
            raise ValidationError("Avatar format must be JPG, PNG, or WebP.")
        if width > MAX_AVATAR_DIMENSION or height > MAX_AVATAR_DIMENSION:
            raise ValidationError("Avatar dimensions must not exceed 4096 × 4096 pixels.")

        return avatar

    @transaction.atomic
    def save(self):
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        self.user.save(update_fields=["first_name", "last_name"])

        self.profile.bio = self.cleaned_data["bio"].strip()
        self.profile.website = self.cleaned_data["website"].strip()

        old_avatar_name = self.profile.avatar.name if self.profile.avatar else None
        new_avatar = self.cleaned_data.get("avatar")
        remove_avatar = self.cleaned_data.get("remove_avatar", False)

        if remove_avatar:
            self.profile.avatar = ""
        elif new_avatar:
            self.profile.avatar = new_avatar

        self.profile.save()

        if old_avatar_name and (remove_avatar or new_avatar):
            storage = self.profile._meta.get_field("avatar").storage
            if old_avatar_name != self.profile.avatar.name:
                storage.delete(old_avatar_name)

        return self.profile
