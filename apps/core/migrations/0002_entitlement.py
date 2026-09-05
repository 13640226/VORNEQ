from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("marketplace", "0002_productreview_alter_product_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Entitlement",
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
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entitlements",
                        to="marketplace.product",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entitlements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="entitlement",
            constraint=models.UniqueConstraint(
                fields=("user", "product"),
                name="core_ent_user_product_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="entitlement",
            index=models.Index(
                fields=["user", "product", "is_active"],
                name="core_ent_user_prod_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="entitlement",
            index=models.Index(
                fields=["expires_at"],
                name="core_ent_expires_idx",
            ),
        ),
    ]
