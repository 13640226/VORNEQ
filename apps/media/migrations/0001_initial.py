# Generated manually to match apps.media models.

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MediaAsset",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "media_type",
                    models.CharField(
                        choices=[("image", "Image"), ("video", "Video")],
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(blank=True, max_length=200)),
                ("alt_text", models.CharField(blank=True, max_length=500)),
                ("file", models.FileField(upload_to="media_assets/%Y/%m/%d/")),
                ("mime_type", models.CharField(max_length=120)),
                ("byte_size", models.PositiveBigIntegerField()),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                ("duration_ms", models.PositiveBigIntegerField(blank=True, null=True)),
                ("presentation_metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["media_type", "is_active"],
                        name="media_type_active_idx",
                    ),
                    models.Index(fields=["created_at"], name="media_created_idx"),
                ],
            },
        ),
    ]
