from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_contextual_reputation"),
        ("evidence", "0004_prediction_ledger"),
        ("verification", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QualitySignal",
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
                    "signal_type",
                    models.CharField(
                        choices=[
                            ("external_reference", "External reference"),
                            ("reproducibility", "Reproducibility"),
                            ("adjudication", "Adjudication"),
                            ("independent_corroboration", "Independent corroboration"),
                            ("proxy_statistical", "Statistical or proxy"),
                            ("contestation_correction", "Contestation or correction"),
                            ("consensus", "Consensus"),
                        ],
                        max_length=50,
                    ),
                ),
                ("source_ref", models.CharField(max_length=255)),
                ("provenance_ref", models.CharField(blank=True, max_length=500)),
                ("independence_declared", models.BooleanField(default=False)),
                ("independence_basis", models.TextField(blank=True)),
                ("domain", models.SlugField(max_length=100)),
                ("observed_at", models.DateTimeField(default=timezone.now)),
                (
                    "policy_version",
                    models.CharField(default="eligibility-v1", max_length=40),
                ),
                ("is_eligible", models.BooleanField(default=False, editable=False)),
                (
                    "eligibility_reasons",
                    models.JSONField(blank=True, default=list, editable=False),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assessor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="quality_signals_assessed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "evidence_relation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quality_signals",
                        to="evidence.evidencerelation",
                    ),
                ),
                (
                    "method",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quality_signals",
                        to="verification.verificationmethod",
                    ),
                ),
                (
                    "verification_result",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quality_signals",
                        to="verification.verificationresult",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="qualitysignal",
            constraint=models.UniqueConstraint(
                fields=(
                    "verification_result",
                    "signal_type",
                    "source_ref",
                    "method",
                    "policy_version",
                ),
                name="core_quality_signal_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="qualitysignal",
            index=models.Index(
                fields=["verification_result", "signal_type"],
                name="core_quality_result_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="qualitysignal",
            index=models.Index(
                fields=["domain", "method"],
                name="core_quality_domain_method_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="qualitysignal",
            index=models.Index(
                fields=["is_eligible", "created_at"],
                name="core_quality_eligible_time_idx",
            ),
        ),
    ]
