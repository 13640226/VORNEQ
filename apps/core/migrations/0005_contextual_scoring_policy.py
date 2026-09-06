from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_quality_signal"),
    ]

    operations = [
        migrations.AddField(
            model_name="qualitysignal",
            name="direction",
            field=models.CharField(
                choices=[
                    ("supports_result", "Supports result"),
                    ("contradicts_result", "Contradicts result"),
                    ("inconclusive", "Inconclusive"),
                ],
                default="inconclusive",
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name="ScoringPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.SlugField(max_length=100)),
                ("version", models.CharField(max_length=40)),
                ("active", models.BooleanField(default=False)),
                ("direction_weights", models.JSONField(default=dict)),
                ("base_weight", models.FloatField(default=1.0)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "verification_method",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scoring_policies",
                        to="verification.verificationmethod",
                    ),
                ),
            ],
            options={
                "ordering": ["domain", "verification_method_id", "version"],
            },
        ),
        migrations.AddConstraint(
            model_name="scoringpolicy",
            constraint=models.UniqueConstraint(
                fields=("domain", "verification_method", "version"),
                name="core_score_policy_scope_version_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="scoringpolicy",
            index=models.Index(
                fields=["domain", "verification_method", "version"],
                name="core_score_policy_scope_idx",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="contextualreputationevent",
            name="core_ctx_rep_event_unique",
        ),
        migrations.AddField(
            model_name="contextualreputationevent",
            name="quality_signal",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reputation_events",
                to="core.qualitysignal",
            ),
        ),
        migrations.AddField(
            model_name="contextualreputationevent",
            name="scoring_policy",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reputation_events",
                to="core.scoringpolicy",
            ),
        ),
        migrations.AddField(
            model_name="contextualreputationevent",
            name="old_score",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contextualreputationevent",
            name="delta",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contextualreputationevent",
            name="new_score",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="contextualreputationevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("verification_submitted", "Verification submitted"),
                    ("score_applied", "Score applied"),
                ],
                default="verification_submitted",
                max_length=50,
            ),
        ),
        migrations.AddConstraint(
            model_name="contextualreputationevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("event_type", "verification_submitted")),
                fields=("contextual_reputation", "verification_result", "event_type"),
                name="core_ctx_rep_activity_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="contextualreputationevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("event_type", "score_applied")),
                fields=("contextual_reputation", "quality_signal", "scoring_policy"),
                name="core_ctx_rep_score_event_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="contextualreputationevent",
            index=models.Index(
                fields=["quality_signal", "scoring_policy"],
                name="core_ctx_rep_score_signal_idx",
            ),
        ),
    ]
