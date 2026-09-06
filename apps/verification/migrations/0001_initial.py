# Generated manually to match apps.verification models.

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("evidence", "0004_prediction_ledger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VerificationMethod",
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
                ("code", models.SlugField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=150)),
                ("description", models.TextField(blank=True)),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("automated", "Automated"),
                            ("hybrid", "Hybrid"),
                        ],
                        default="manual",
                        max_length=20,
                    ),
                ),
                ("version", models.CharField(blank=True, max_length=50)),
                ("is_active", models.BooleanField(default=True)),
                ("metadata_schema", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="VerificationRequest",
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
                ("artifact_object_id", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requested", "Requested"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="requested",
                        max_length=20,
                    ),
                ),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("context", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "artifact_content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="verification_requests",
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "claim",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="verification_requests",
                        to="evidence.claim",
                    ),
                ),
                (
                    "method",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="requests",
                        to="verification.verificationmethod",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="verification_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["status", "created_at"],
                        name="verify_req_status_time_idx",
                    ),
                    models.Index(
                        fields=["artifact_content_type", "artifact_object_id"],
                        name="verify_req_artifact_idx",
                    ),
                    models.Index(fields=["claim"], name="verify_req_claim_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="VerificationResult",
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
                    "outcome",
                    models.CharField(
                        choices=[
                            ("pass", "Pass"),
                            ("fail", "Fail"),
                            ("partial", "Partial"),
                            ("inconclusive", "Inconclusive"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "reported_confidence",
                    models.PositiveSmallIntegerField(
                        help_text="Verifier-reported confidence from 0 to 100.",
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                ("summary", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="results",
                        to="verification.verificationrequest",
                    ),
                ),
                (
                    "verifier",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="verification_results",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["request", "outcome"],
                        name="verify_result_req_out_idx",
                    ),
                    models.Index(
                        fields=["verifier", "created_at"],
                        name="verify_result_actor_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="VerificationEvidence",
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
                    "visibility",
                    models.CharField(
                        choices=[
                            ("private", "Private"),
                            ("participants", "Participants"),
                            ("public", "Public"),
                        ],
                        default="private",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "evidence_relation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="verification_links",
                        to="evidence.evidencerelation",
                    ),
                ),
                (
                    "result",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evidence_links",
                        to="verification.verificationresult",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["result", "visibility"],
                        name="verify_evidence_visibility_idx",
                    ),
                    models.Index(
                        fields=["evidence_relation"],
                        name="verify_evidence_relation_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("result", "evidence_relation"),
                        name="uniq_verify_result_evidence_relation",
                    )
                ],
            },
        ),
    ]
