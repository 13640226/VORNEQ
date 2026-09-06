import uuid

from django.core.exceptions import ValidationError
from django.db import models


class MediaAsset(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    media_type = models.CharField(max_length=20, choices=MediaType.choices)
    title = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(max_length=500, blank=True)
    file = models.FileField(upload_to="media_assets/%Y/%m/%d/")
    mime_type = models.CharField(max_length=120)
    byte_size = models.PositiveBigIntegerField()
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration_ms = models.PositiveBigIntegerField(null=True, blank=True)
    presentation_metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["media_type", "is_active"], name="media_type_active_idx"),
            models.Index(fields=["created_at"], name="media_created_idx"),
        ]

    def clean(self):
        super().clean()
        if self.media_type == self.MediaType.IMAGE:
            if not self.mime_type.startswith("image/"):
                raise ValidationError({"mime_type": "Image assets require an image MIME type."})
            if self.width is None or self.height is None:
                raise ValidationError(
                    {"width": "Image assets require intrinsic width and height."}
                )
            if self.duration_ms is not None:
                raise ValidationError(
                    {"duration_ms": "Image assets cannot define a duration."}
                )
        elif self.media_type == self.MediaType.VIDEO:
            if not self.mime_type.startswith("video/"):
                raise ValidationError({"mime_type": "Video assets require a video MIME type."})

    def __str__(self):
        return self.title or f"{self.media_type}:{self.id}"


class MediaEmbedding(models.Model):
    """Derived, rebuildable similarity data for a MediaAsset.

    This is operational discovery infrastructure. It is not Evidence,
    Verification, Provenance, Reputation, or a canonical trust record.
    """

    media_asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.CASCADE,
        related_name="similarity_embeddings",
    )
    embedding_policy = models.CharField(max_length=200)
    provider = models.CharField(max_length=100)
    model = models.CharField(max_length=120)
    model_version = models.CharField(max_length=120)
    dimensions = models.PositiveIntegerField()
    vector = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["media_asset", "embedding_policy"],
                name="uniq_media_embedding_policy",
            )
        ]
        indexes = [
            models.Index(fields=["embedding_policy"], name="media_embed_policy_idx"),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.vector, list) or not self.vector:
            raise ValidationError({"vector": "Embedding vector must be a non-empty list."})
        if len(self.vector) != self.dimensions:
            raise ValidationError(
                {"dimensions": "Embedding dimensions must match the stored vector length."}
            )
        if any(not isinstance(value, (int, float)) for value in self.vector):
            raise ValidationError({"vector": "Embedding vector values must be numeric."})

    def __str__(self):
        return f"{self.media_asset_id}:{self.embedding_policy}"
