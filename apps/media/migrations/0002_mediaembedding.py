from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("media", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MediaEmbedding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("embedding_policy", models.CharField(max_length=200)),
                ("provider", models.CharField(max_length=100)),
                ("model", models.CharField(max_length=120)),
                ("model_version", models.CharField(max_length=120)),
                ("dimensions", models.PositiveIntegerField()),
                ("vector", models.JSONField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "media_asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="similarity_embeddings",
                        to="media.mediaasset",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="mediaembedding",
            constraint=models.UniqueConstraint(
                fields=("media_asset", "embedding_policy"),
                name="uniq_media_embedding_policy",
            ),
        ),
        migrations.AddIndex(
            model_name="mediaembedding",
            index=models.Index(fields=["embedding_policy"], name="media_embed_policy_idx"),
        ),
    ]
