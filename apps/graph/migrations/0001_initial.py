import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="Node",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("node_type", models.CharField(choices=[("claim", "Claim"), ("evidence", "Evidence"), ("provenance", "Provenance"), ("user", "User"), ("library_item", "Library item"), ("audio_item", "Audio item"), ("perspective", "Perspective"), ("critique", "Critique"), ("condition", "Change condition"), ("other", "Other")], max_length=32)),
                ("object_id", models.CharField(max_length=64)),
                ("label", models.CharField(max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("refreshed_at", models.DateTimeField(auto_now=True)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
            ],
            options={
                "ordering": ["node_type", "label", "id"],
                "indexes": [models.Index(fields=["node_type"], name="graph_node_type_idx")],
                "constraints": [models.UniqueConstraint(fields=("content_type", "object_id"), name="graph_node_unique_object")],
            },
        ),
        migrations.CreateModel(
            name="Edge",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("supports", "Supports"), ("contradicts", "Contradicts"), ("contextualizes", "Contextualizes"), ("unclear", "Unclear"), ("has_provenance", "Has provenance"), ("has_perspective", "Has perspective"), ("has_critique", "Has critique"), ("has_condition", "Has condition"), ("created_by", "Created by"), ("related_to", "Related to")], max_length=32)),
                ("canonical_ref", models.CharField(blank=True, default="", max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("refreshed_at", models.DateTimeField(auto_now=True)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outgoing_edges", to="graph.node")),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incoming_edges", to="graph.node")),
            ],
            options={
                "ordering": ["kind", "id"],
                "indexes": [
                    models.Index(fields=["source", "kind"], name="graph_edge_source_kind_idx"),
                    models.Index(fields=["target", "kind"], name="graph_edge_target_kind_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("source", "target", "kind", "canonical_ref"), name="graph_edge_unique_projection")],
            },
        ),
    ]
