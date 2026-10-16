from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0006_dispute"),
    ]

    operations = [
        migrations.AddField(
            model_name="provenancestep",
            name="public_source_ref",
            field=models.CharField(
                max_length=255,
                null=True,
                blank=True,
                verbose_name="ارجاع عمومی منبع",
                help_text="Public-safe source reference representation only; raw source_ref remains undisclosed.",
            ),
        ),
    ]
