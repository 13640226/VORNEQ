import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("evidence", "0003_critique_category"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Prediction",
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
                    "event_statement",
                    models.TextField(
                        help_text="A falsifiable event that can be resolved as occurred or did not occur."
                    ),
                ),
                (
                    "probability",
                    models.DecimalField(
                        decimal_places=4,
                        help_text="Forecast probability from 0 to 1.",
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                ("resolution_date", models.DateTimeField()),
                ("rationale", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "claim",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="predictions",
                        to="evidence.claim",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="predictions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["resolution_date", "created_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="PredictionResolution",
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
                ("outcome_occurred", models.BooleanField()),
                ("notes", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "evidence_ref",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="prediction_resolutions",
                        to="evidence.evidence",
                    ),
                ),
                (
                    "prediction",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="resolution",
                        to="evidence.prediction",
                    ),
                ),
                (
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="prediction_resolutions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["resolved_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="prediction",
            index=models.Index(
                fields=["claim", "resolution_date"],
                name="prediction_claim_due_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="prediction",
            index=models.Index(
                fields=["created_by", "created_at"],
                name="prediction_author_time_idx",
            ),
        ),
    ]
