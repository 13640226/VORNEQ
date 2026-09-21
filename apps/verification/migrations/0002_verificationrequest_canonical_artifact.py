import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_identityhandle"),
        ("verification", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="verificationrequest",
            name="canonical_artifact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="verification_requests",
                to="core.artifact",
            ),
        ),
    ]
