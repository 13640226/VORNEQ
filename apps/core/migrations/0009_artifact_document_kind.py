from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_contextual_reputation_identity_actor_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="artifact",
            name="kind",
            field=models.CharField(
                choices=[
                    ("product", "Product"),
                    ("library_item", "Library item"),
                    ("document", "Document"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=40,
            ),
        ),
    ]
