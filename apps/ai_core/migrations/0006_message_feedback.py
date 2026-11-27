"""Additive feedback table; operational migration requires separate authorization."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ai_core", "0005_chat_job_v1")]
    operations = [
        migrations.CreateModel(
            name="AIMessageFeedback",
            fields=[
                ("message", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True, related_name="feedback", serialize=False, to="ai_core.aimessage")),
                ("rating", models.CharField(choices=[("like", "Like"), ("dislike", "Dislike")],
                                           max_length=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"constraints": [
                models.CheckConstraint(condition=models.Q(rating__in=["like", "dislike"]),
                                       name="ai_msg_feedback_rating_valid"),
            ]},
        ),
    ]
