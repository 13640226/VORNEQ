# Generated manually for the initial Documents domain boundary.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField(blank=True)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="documents_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
                "indexes": [
                    models.Index(fields=["created_by", "is_active"], name="docs_owner_active_idx"),
                    models.Index(fields=["is_active", "updated_at"], name="docs_active_time_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DocumentAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("owner", "Owner"), ("editor", "Editor"), ("viewer", "Viewer")], max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="access_entries", to="documents.document")),
                ("granted_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="document_access_grants", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="document_access_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "role"], name="docs_access_user_role_idx"),
                    models.Index(fields=["document", "role"], name="docs_access_doc_role_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("document", "user"), name="docs_access_document_user_unique"),
                    models.UniqueConstraint(condition=models.Q(("role", "owner")), fields=("document",), name="docs_access_single_owner"),
                ],
            },
        ),
    ]
