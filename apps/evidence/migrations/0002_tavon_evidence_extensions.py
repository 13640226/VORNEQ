import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("evidence", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EvidenceState",
            fields=[
                (
                    "claim",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="evidence_state",
                        serialize=False,
                        to="evidence.claim",
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("no_evidence", "No evidence"),
                            ("supporting_only", "Supporting only"),
                            ("contradicting_only", "Contradicting only"),
                            ("neutral_only", "Neutral only"),
                            ("supporting_neutral", "Supporting + neutral"),
                            ("contradicting_neutral", "Contradicting + neutral"),
                            ("mixed", "Mixed"),
                        ],
                        default="no_evidence",
                        max_length=32,
                    ),
                ),
                ("supporting_count", models.PositiveIntegerField(default=0)),
                ("contradicting_count", models.PositiveIntegerField(default=0)),
                ("neutral_count", models.PositiveIntegerField(default=0)),
                ("evidence_count", models.PositiveIntegerField(default=0)),
                ("refreshed_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Evidence state",
                "verbose_name_plural": "Evidence states",
            },
        ),
        migrations.CreateModel(
            name="Perspective",
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
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="perspectives_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="ContentVersion",
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
                ("version_number", models.PositiveIntegerField()),
                ("snapshot", models.JSONField()),
                ("change_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "claim",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="content_versions",
                        to="evidence.claim",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="claim_versions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["claim_id", "version_number"]},
        ),
        migrations.CreateModel(
            name="ClaimPerspective",
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
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "claim",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="perspective_links",
                        to="evidence.claim",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="claim_perspectives_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "perspective",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="claim_links",
                        to="evidence.perspective",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Critique",
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
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "claim",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="critiques",
                        to="evidence.claim",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="critiques_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="replies",
                        to="evidence.critique",
                    ),
                ),
                (
                    "relation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="critiques",
                        to="evidence.evidencerelation",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="contentversion",
            constraint=models.UniqueConstraint(
                fields=("claim", "version_number"),
                name="contentversion_unique_claim_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="claimperspective",
            constraint=models.UniqueConstraint(
                fields=("claim", "perspective"),
                name="claimperspective_unique_pair",
            ),
        ),
        migrations.AddConstraint(
            model_name="critique",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("claim__isnull", False), ("relation__isnull", True))
                    | models.Q(("claim__isnull", True), ("relation__isnull", False))
                ),
                name="critique_exactly_one_target",
            ),
        ),
    ]
