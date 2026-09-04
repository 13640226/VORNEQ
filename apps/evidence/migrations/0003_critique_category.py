from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("evidence", "0002_tavon_evidence_extensions"),
    ]

    operations = [
        migrations.AddField(
            model_name="critique",
            name="category",
            field=models.CharField(
                choices=[
                    ("data", "Data"),
                    ("definition", "Definition"),
                    ("method", "Method"),
                    ("interpretation", "Interpretation"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=20,
            ),
        ),
    ]
