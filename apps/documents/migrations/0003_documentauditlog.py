from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_artifact_document_kind"),
        ("documents", "0002_identity_subjects"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentAuditLog",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("updated", "Updated"),
                            ("deactivated", "Deactivated"),
                            ("shared", "Shared"),
                            ("revoked", "Revoked"),
                            ("viewed", "Viewed"),
                        ],
                        max_length=20,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor_identity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_audit_events",
                        to="core.identity",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_log",
                        to="documents.document",
                    ),
                ),
            ],
            options={
                "ordering": ["-timestamp", "-id"],
                "indexes": [
                    models.Index(
                        fields=["document", "timestamp"],
                        name="docs_audit_doc_time_idx",
                    ),
                    models.Index(
                        fields=["actor_identity", "timestamp"],
                        name="docs_audit_actor_time_idx",
                    ),
                ],
            },
        ),
    ]
