import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("evidence", "0005_signature_envelope"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dispute",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("critique", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="dispute", to="evidence.critique")),
                ("opened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="disputes_opened", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-opened_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="dispute",
            index=models.Index(fields=["opened_at"], name="dispute_opened_idx"),
        ),
    ]
