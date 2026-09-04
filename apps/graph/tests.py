from django.test import TestCase
from django.urls import reverse

from apps.evidence.models import Claim, EvidenceRelation, EvidenceState
from apps.evidence.services import EvidenceService, RelationService

from .models import Edge, Node
from .services import TruthGraphService


class TruthGraphServiceTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(
            claim_text="A battery chemistry can retain 90% capacity after 1,000 cycles",
            scope="technical diligence pilot",
        )
        self.evidence = EvidenceService.create_with_provenance(
            content="Independent cycle test reports 91% retained capacity after 1,000 cycles.",
            source_ref="https://example.com/public-test-report",
        )
        self.relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            relation_basis="Independent bench test",
        )

    def test_transient_graph_is_read_only(self):
        self.assertEqual(Node.objects.count(), 0)
        self.assertEqual(Edge.objects.count(), 0)

        graph = TruthGraphService.build_claim_graph(self.claim)

        self.assertEqual(graph["root"], f"claim:{self.claim.pk}")
        self.assertEqual(len(graph["nodes"]), 3)
        self.assertEqual(len(graph["edges"]), 2)
        self.assertEqual(Node.objects.count(), 0)
        self.assertEqual(Edge.objects.count(), 0)

    def test_projection_is_rebuildable_cache(self):
        root = TruthGraphService.project_claim(self.claim)

        self.assertEqual(root.node_type, Node.NodeType.CLAIM)
        self.assertEqual(Node.objects.count(), 3)
        self.assertEqual(Edge.objects.count(), 2)

        RelationService.retire(relation=self.relation)
        root = TruthGraphService.project_claim(self.claim)

        self.assertEqual(root.node_type, Node.NodeType.CLAIM)
        self.assertFalse(Edge.objects.filter(source=root).exists())

    def test_graph_endpoint_combines_canonical_evidence_without_writes(self):
        response = self.client.get(
            reverse("graph:claim-graph", kwargs={"claim_id": self.claim.pk})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["root"], f"claim:{self.claim.pk}")
        self.assertEqual(Node.objects.count(), 0)
        self.assertEqual(Edge.objects.count(), 0)

    def test_decision_package_endpoint_includes_state_and_truth_graph(self):
        response = self.client.get(
            reverse("graph:decision-package", kwargs={"claim_id": self.claim.pk})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["evidence_state"]["state"],
            EvidenceState.State.SUPPORTING_ONLY,
        )
        self.assertEqual(payload["truth_graph"]["root"], f"claim:{self.claim.pk}")
        self.assertEqual(len(payload["evidence"]), 1)
