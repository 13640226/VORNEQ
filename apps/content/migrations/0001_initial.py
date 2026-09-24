# Generated manually to match apps.content models.

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="content.category",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "categories",
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=60, unique=True)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="Article",
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
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, max_length=200, unique=True)),
                ("summary", models.TextField(max_length=500)),
                ("content", models.TextField()),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="articles/%Y/%m/%d/",
                    ),
                ),
                ("is_published", models.BooleanField(default=False)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("scheduled_at", models.DateTimeField(blank=True, null=True)),
                ("editorial_metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="articles",
                        to="content.category",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="articles",
                        to="content.tag",
                    ),
                ),
            ],
            options={
                "ordering": ["-published_at", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["is_published", "published_at"],
                        name="content_art_pub_time_idx",
                    )
                ],
            },
        ),
    ]
