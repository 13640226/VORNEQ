from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0008_contextual_reputation_identity_actor_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="Note",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("content", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("artifact", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="note", to="core.artifact")),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
                "indexes": [models.Index(fields=["is_active", "updated_at"], name="notes_active_time_idx")],
            },
        ),
    ]
