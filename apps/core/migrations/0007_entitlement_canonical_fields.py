from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_artifact_identity_registry"),
    ]

    operations = [
        migrations.AddField(
            model_name="entitlement",
            name="artifact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entitlements",
                to="core.artifact",
            ),
        ),
        migrations.AddField(
            model_name="entitlement",
            name="identity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entitlements",
                to="core.identity",
            ),
        ),
        migrations.AddConstraint(
            model_name="entitlement",
            constraint=models.UniqueConstraint(
                condition=models.Q(identity__isnull=False, artifact__isnull=False),
                fields=("identity", "artifact"),
                name="core_ent_identity_artifact_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="entitlement",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(identity__isnull=True, artifact__isnull=True)
                    | models.Q(identity__isnull=False, artifact__isnull=False)
                ),
                name="core_ent_canonical_pair_complete",
            ),
        ),
        migrations.AddIndex(
            model_name="entitlement",
            index=models.Index(
                fields=["identity", "artifact", "is_active"],
                name="core_ent_id_art_active_idx",
            ),
        ),
    ]
