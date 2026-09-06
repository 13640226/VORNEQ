# Generated for VORNEQ profile presentation data.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.profiles.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
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
                (
                    "avatar",
                    models.ImageField(
                        blank=True,
                        upload_to=apps.profiles.models.avatar_upload_to,
                    ),
                ),
                ("bio", models.TextField(blank=True, max_length=500)),
                ("website", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile_data",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
