from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_entitlement"),
        ("verification", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContextualReputation",
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
                ("domain", models.SlugField(max_length=100)),
                ("score", models.FloatField(default=0.0)),
                ("sample_count", models.PositiveIntegerField(default=0)),
                ("last_event_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contextual_reputations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "verification_method",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contextual_reputations",
                        to="verification.verificationmethod",
                    ),
                ),
            ],
            options={
                "ordering": ["user_id", "domain", "verification_method_id"],
            },
        ),
        migrations.CreateModel(
            name="ContextualReputationEvent",
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
                            ("verification_submitted", "Verification submitted")
                        ],
                        default="verification_submitted",
                        max_length=50,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contextual_reputation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="core.contextualreputation",
                    ),
                ),
                (
                    "verification_result",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reputation_events",
                        to="verification.verificationresult",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="contextualreputation",
            constraint=models.UniqueConstraint(
                fields=("user", "domain", "verification_method"),
                name="core_ctx_rep_user_domain_method_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="contextualreputation",
            index=models.Index(
                fields=["user", "domain"],
                name="core_ctx_rep_user_domain_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="contextualreputation",
            index=models.Index(
                fields=["verification_method", "last_event_at"],
                name="core_ctx_rep_method_time_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="contextualreputationevent",
            constraint=models.UniqueConstraint(
                fields=(
                    "contextual_reputation",
                    "verification_result",
                    "event_type",
                ),
                name="core_ctx_rep_event_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="contextualreputationevent",
            index=models.Index(
                fields=["contextual_reputation", "created_at"],
                name="core_ctx_rep_event_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="contextualreputationevent",
            index=models.Index(
                fields=["verification_result"],
                name="core_ctx_rep_result_idx",
            ),
        ),
    ]
