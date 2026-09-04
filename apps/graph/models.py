import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Node(models.Model):
    """Optional persisted projection node for the Truth Graph.

    Canonical domain models remain the source of truth. Nodes are rebuildable
    projections that can point at UUID- or integer-keyed Django models.
    """

    class NodeType(models.TextChoices):
        CLAIM = "claim", "Claim"
        EVIDENCE = "evidence", "Evidence"
        PROVENANCE = "provenance", "Provenance"
        USER = "user", "User"
        LIBRARY_ITEM = "library_item", "Library item"
        AUDIO_ITEM = "audio_item", "Audio item"
        PERSPECTIVE = "perspective", "Perspective"
        CRITIQUE = "critique", "Critique"
        CONDITION = "condition", "Change condition"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    node_type = models.CharField(max_length=32, choices=NodeType.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    content_object = GenericForeignKey("content_type", "object_id")
    label = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    refreshed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["node_type", "label", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="graph_node_unique_object",
            )
        ]
        indexes = [
            models.Index(fields=["node_type"], name="graph_node_type_idx"),
        ]

    def __str__(self):
        return f"{self.node_type}: {self.label}"


class Edge(models.Model):
    """Rebuildable relation between projected graph nodes."""

    class Kind(models.TextChoices):
        SUPPORTS = "supports", "Supports"
        CONTRADICTS = "contradicts", "Contradicts"
        CONTEXTUALIZES = "contextualizes", "Contextualizes"
        UNCLEAR = "unclear", "Unclear"
        HAS_PROVENANCE = "has_provenance", "Has provenance"
        HAS_PERSPECTIVE = "has_perspective", "Has perspective"
        HAS_CRITIQUE = "has_critique", "Has critique"
        HAS_CONDITION = "has_condition", "Has condition"
        CREATED_BY = "created_by", "Created by"
        RELATED_TO = "related_to", "Related to"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="outgoing_edges")
    target = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="incoming_edges")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    canonical_ref = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    refreshed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target", "kind", "canonical_ref"],
                name="graph_edge_unique_projection",
            )
        ]
        indexes = [
            models.Index(fields=["source", "kind"], name="graph_edge_source_kind_idx"),
            models.Index(fields=["target", "kind"], name="graph_edge_target_kind_idx"),
        ]

    def __str__(self):
        return f"{self.source_id} -[{self.kind}]-> {self.target_id}"
