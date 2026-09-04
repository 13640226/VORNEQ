from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from apps.evidence.models import Claim, EvidenceRelation

from .models import Edge, Node


class TruthGraphService:
    """Build read-only claim graphs and optionally persist rebuildable projections."""

    @staticmethod
    def _node_payload(obj, node_type, label, metadata=None):
        return {
            "id": f"{node_type}:{obj.pk}",
            "node_type": node_type,
            "object_id": str(obj.pk),
            "label": label,
            "metadata": metadata or {},
        }

    @classmethod
    def build_claim_graph(cls, claim: Claim):
        """Return a transient graph without writing to the database."""
        nodes = []
        edges = []
        seen = set()

        def add_node(payload):
            if payload["id"] not in seen:
                seen.add(payload["id"])
                nodes.append(payload)

        claim_node = cls._node_payload(
            claim,
            Node.NodeType.CLAIM,
            claim.claim_text[:255],
            {"scope": claim.scope},
        )
        add_node(claim_node)

        relations = (
            EvidenceRelation.objects.filter(claim=claim, retired_at__isnull=True)
            .select_related("evidence", "created_by")
            .prefetch_related("evidence__provenance_chain")
            .order_by("created_at", "id")
        )

        for relation in relations:
            evidence = relation.evidence
            evidence_node = cls._node_payload(
                evidence,
                Node.NodeType.EVIDENCE,
                evidence.content[:255] or str(evidence.pk),
                {
                    "content_type": evidence.content_type,
                    "integrity_digest": evidence.integrity_digest,
                },
            )
            add_node(evidence_node)
            edges.append(
                {
                    "source": claim_node["id"],
                    "target": evidence_node["id"],
                    "kind": relation.relation,
                    "canonical_ref": str(relation.pk),
                    "metadata": {"relation_basis": relation.relation_basis},
                }
            )

            for step in evidence.provenance_chain.all():
                step_node = cls._node_payload(
                    step,
                    Node.NodeType.PROVENANCE,
                    step.source_ref[:255],
                    {
                        "source_type": step.source_type,
                        "transformation": step.transformation,
                        "timestamp": step.timestamp.isoformat(),
                    },
                )
                add_node(step_node)
                edges.append(
                    {
                        "source": evidence_node["id"],
                        "target": step_node["id"],
                        "kind": Edge.Kind.HAS_PROVENANCE,
                        "canonical_ref": str(step.pk),
                        "metadata": {},
                    }
                )

        for link in claim.perspective_links.select_related("perspective").all():
            perspective = link.perspective
            perspective_node = cls._node_payload(
                perspective,
                Node.NodeType.PERSPECTIVE,
                perspective.name,
                {"description": perspective.description},
            )
            add_node(perspective_node)
            edges.append(
                {
                    "source": claim_node["id"],
                    "target": perspective_node["id"],
                    "kind": Edge.Kind.HAS_PERSPECTIVE,
                    "canonical_ref": str(link.pk),
                    "metadata": {"note": link.note},
                }
            )

        for condition in claim.change_conditions.all().order_by("created_at", "id"):
            condition_node = cls._node_payload(
                condition,
                Node.NodeType.CONDITION,
                condition.description[:255],
                {"severity": condition.severity, "evidence_required": condition.evidence_required},
            )
            add_node(condition_node)
            edges.append(
                {
                    "source": claim_node["id"],
                    "target": condition_node["id"],
                    "kind": Edge.Kind.HAS_CONDITION,
                    "canonical_ref": str(condition.pk),
                    "metadata": {},
                }
            )

        return {
            "root": claim_node["id"],
            "nodes": nodes,
            "edges": edges,
        }

    @classmethod
    @transaction.atomic
    def project_claim(cls, claim: Claim):
        """Persist the current transient graph as a rebuildable projection."""
        graph = cls.build_claim_graph(claim)
        node_map = {}

        model_map = {
            Node.NodeType.CLAIM: ("evidence", "claim"),
            Node.NodeType.EVIDENCE: ("evidence", "evidence"),
            Node.NodeType.PROVENANCE: ("evidence", "provenancestep"),
            Node.NodeType.PERSPECTIVE: ("evidence", "perspective"),
            Node.NodeType.CONDITION: ("evidence", "changecondition"),
        }

        for item in graph["nodes"]:
            app_label, model = model_map[item["node_type"]]
            content_type = ContentType.objects.get(app_label=app_label, model=model)
            node, _ = Node.objects.update_or_create(
                content_type=content_type,
                object_id=item["object_id"],
                defaults={
                    "node_type": item["node_type"],
                    "label": item["label"],
                    "metadata": item["metadata"],
                },
            )
            node_map[item["id"]] = node

        projected_ids = []
        for item in graph["edges"]:
            edge, _ = Edge.objects.update_or_create(
                source=node_map[item["source"]],
                target=node_map[item["target"]],
                kind=item["kind"],
                canonical_ref=item["canonical_ref"],
                defaults={"metadata": item["metadata"]},
            )
            projected_ids.append(edge.pk)

        root = node_map[graph["root"]]
        Edge.objects.filter(source=root).exclude(pk__in=projected_ids).delete()
        return root
