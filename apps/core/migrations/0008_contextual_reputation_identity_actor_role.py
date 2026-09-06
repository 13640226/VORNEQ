from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_entitlement_canonical_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="contextualreputation",
            name="actor_role",
            field=models.CharField(
                choices=[
                    ("verifier", "Verifier"),
                    ("seller", "Seller"),
                    ("creator", "Creator"),
                    ("publisher", "Publisher"),
                    ("author", "Author"),
                ],
                default="verifier",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="contextualreputation",
            name="identity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contextual_reputations",
                to="core.identity",
            ),
        ),
        migrations.AddConstraint(
            model_name="contextualreputation",
            constraint=models.UniqueConstraint(
                condition=models.Q(identity__isnull=False),
                fields=("identity", "actor_role", "domain", "verification_method"),
                name="core_ctx_rep_identity_role_domain_method_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="contextualreputation",
            index=models.Index(
                fields=["identity", "actor_role"],
                name="core_ctx_rep_identity_role_idx",
            ),
        ),
    ]
