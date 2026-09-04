import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Reputation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accuracy_score", models.FloatField(default=0.0)),
                ("corrigibility_score", models.FloatField(default=0.0)),
                ("source_quality_score", models.FloatField(default=0.0)),
                ("fair_critique_score", models.FloatField(default=0.0)),
                ("domain_expertise_score", models.FloatField(default=0.0)),
                ("prediction_accuracy_score", models.FloatField(default=0.0)),
                ("social_behavior_score", models.FloatField(default=0.0)),
                ("overall_score", models.FloatField(default=0.0)),
                ("last_updated", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reputation",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ReputationHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "dimension",
                    models.CharField(
                        choices=[
                            ("accuracy", "Accuracy"),
                            ("corrigibility", "Corrigibility"),
                            ("source_quality", "Source Quality"),
                            ("fair_critique", "Fair Critique"),
                            ("domain_expertise", "Domain Expertise"),
                            ("prediction_accuracy", "Prediction Accuracy"),
                            ("social_behavior", "Social Behavior"),
                        ],
                        max_length=30,
                    ),
                ),
                ("old_value", models.FloatField()),
                ("new_value", models.FloatField()),
                ("event_type", models.CharField(max_length=80)),
                ("event_id", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reputation_history",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="reputation",
            index=models.Index(fields=["user", "last_updated"], name="core_rep_user_time_idx"),
        ),
        migrations.AddIndex(
            model_name="reputationhistory",
            index=models.Index(fields=["user", "dimension", "created_at"], name="core_rep_hist_user_dim_idx"),
        ),
        migrations.AddConstraint(
            model_name="reputationhistory",
            constraint=models.UniqueConstraint(
                fields=("user", "dimension", "event_type", "event_id"),
                name="core_rep_hist_event_unique",
            ),
        ),
    ]
