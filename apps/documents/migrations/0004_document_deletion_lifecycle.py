from django.db import migrations, models
import django.db.models.deletion


def sync_existing_document_lifecycle(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    Document.objects.filter(is_active=False).update(lifecycle_state="deactivated")


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0003_documentauditlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="lifecycle_state",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("deactivated", "Deactivated"),
                    ("pending_deletion", "Pending deletion"),
                ],
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="previous_lifecycle_state",
            field=models.CharField(
                blank=True,
                choices=[
                    ("active", "Active"),
                    ("deactivated", "Deactivated"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="deletion_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="deletion_requested_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="document_deletion_requests",
                to="core.identity",
            ),
        ),
        migrations.CreateModel(
            name="RetentionHold",
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
                ("reason", models.CharField(max_length=255)),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("legal", "Legal"),
                            ("security", "Security"),
                            ("investigation", "Investigation"),
                        ],
                        max_length=20,
                    ),
                ),
                ("placed_at", models.DateTimeField(auto_now_add=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retention_holds",
                        to="documents.document",
                    ),
                ),
                (
                    "placed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_retention_holds_placed",
                        to="core.identity",
                    ),
                ),
                (
                    "released_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_retention_holds_released",
                        to="core.identity",
                    ),
                ),
            ],
            options={
                "ordering": ["-placed_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["document", "released_at"],
                        name="docs_hold_doc_release_idx",
                    ),
                ],
            },
        ),
        migrations.AlterField(
            model_name="documentauditlog",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("updated", "Updated"),
                    ("deactivated", "Deactivated"),
                    ("shared", "Shared"),
                    ("revoked", "Revoked"),
                    ("viewed", "Viewed"),
                    ("deletion_requested", "Deletion requested"),
                    ("deletion_cancelled", "Deletion cancelled"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(
            sync_existing_document_lifecycle,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
