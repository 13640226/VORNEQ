import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0004_prediction_ledger"),
        ("verification", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SignatureEnvelope",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key_id", models.CharField(max_length=120)),
                ("algorithm", models.CharField(choices=[("ed25519", "Ed25519")], default="ed25519", max_length=20)),
                ("canonical_version", models.CharField(default="trust-signature-v1", max_length=40)),
                ("payload_digest", models.CharField(max_length=64)),
                ("signature", models.TextField()),
                ("signed_at", models.DateTimeField(auto_now_add=True)),
                ("evidence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="signature_envelopes", to="evidence.evidence")),
                ("provenance_step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="signature_envelopes", to="evidence.provenancestep")),
                ("verification_result", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="signature_envelopes", to="verification.verificationresult")),
            ],
            options={"ordering": ["-signed_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="signatureenvelope",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("evidence__isnull", False), ("provenance_step__isnull", True), ("verification_result__isnull", True))
                    | models.Q(("evidence__isnull", True), ("provenance_step__isnull", False), ("verification_result__isnull", True))
                    | models.Q(("evidence__isnull", True), ("provenance_step__isnull", True), ("verification_result__isnull", False))
                ),
                name="evidence_signature_exactly_one_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="signatureenvelope",
            constraint=models.UniqueConstraint(condition=models.Q(("evidence__isnull", False)), fields=("evidence", "key_id", "canonical_version", "payload_digest"), name="evidence_signature_evidence_unique"),
        ),
        migrations.AddConstraint(
            model_name="signatureenvelope",
            constraint=models.UniqueConstraint(condition=models.Q(("provenance_step__isnull", False)), fields=("provenance_step", "key_id", "canonical_version", "payload_digest"), name="evidence_signature_provenance_unique"),
        ),
        migrations.AddConstraint(
            model_name="signatureenvelope",
            constraint=models.UniqueConstraint(condition=models.Q(("verification_result__isnull", False)), fields=("verification_result", "key_id", "canonical_version", "payload_digest"), name="evidence_signature_verification_unique"),
        ),
        migrations.AddIndex(
            model_name="signatureenvelope",
            index=models.Index(fields=["key_id", "signed_at"], name="evidence_signature_key_time_idx"),
        ),
        migrations.AddIndex(
            model_name="signatureenvelope",
            index=models.Index(fields=["payload_digest"], name="evidence_signature_digest_idx"),
        ),
    ]
