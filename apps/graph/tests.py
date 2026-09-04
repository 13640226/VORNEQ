from django.test import TestCase
from django.urls import reverse

from apps.evidence.models import Claim, Critique, EvidenceRelation, EvidenceState
from apps.evidence.services import EvidenceService, RelationService
from library.models import AudioItem, LibraryItem

from .analysis import DisagreementMapService, EvidenceGapFinderService
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

    def test_library_and_audio_items_can_be_projected_without_parallel_models(self):
        library_item = LibraryItem.objects.create(
            title="Battery diligence memo",
            slug="battery-diligence-memo",
        )
        audio_item = AudioItem.objects.create(title="Expert interview")

        library_node = TruthGraphService.project_content_object(
            obj=library_item,
            node_type=Node.NodeType.LIBRARY_ITEM,
            label=library_item.title,
        )
        audio_node = TruthGraphService.project_content_object(
            obj=audio_item,
            node_type=Node.NodeType.AUDIO_ITEM,
            label=audio_item.title,
        )

        self.assertEqual(library_node.content_object, library_item)
        self.assertEqual(audio_node.content_object, audio_item)
        self.assertEqual(library_node.node_type, Node.NodeType.LIBRARY_ITEM)
        self.assertEqual(audio_node.node_type, Node.NodeType.AUDIO_ITEM)

    def test_graph_endpoint_combines_canonical_evidence_without_writes(self):
        response = self.client.get(
            reverse("graph:claim-graph", kwargs={"claim_id": self.claim.pk})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["root"], f"claim:{self.claim.pk}")
        self.assertEqual(Node.objects.count(), 0)
        self.assertEqual(Edge.objects.count(), 0)

    def test_disagreement_map_uses_explicit_human_category(self):
        Critique.objects.create(
            relation=self.relation,
            category=Critique.Category.METHOD,
            body="The cycle-test protocol does not match the claimed operating conditions.",
        )

        result = DisagreementMapService.build(self.claim)

        self.assertEqual(result["category_counts"][Critique.Category.METHOD], 1)
        self.assertEqual(result["category_counts"][Critique.Category.DATA], 0)
        self.assertIn("not automatically assigned", result["note"])

        response = self.client.get(
            reverse("graph:disagreement-map", kwargs={"claim_id": self.claim.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["category_counts"][Critique.Category.METHOD],
            1,
        )

    def test_evidence_gap_finder_flags_one_sided_single_evidence(self):
        result = EvidenceGapFinderService.build(self.claim)
        codes = {gap["code"] for gap in result["gaps"]}

        self.assertIn("no_contradicting_evidence", codes)
        self.assertIn("single_evidence_dependency", codes)
        self.assertNotIn("missing_provenance", codes)

        response = self.client.get(
            reverse("graph:evidence-gaps", kwargs={"claim_id": self.claim.pk})
        )
        self.assertEqual(response.status_code, 200)
        response_codes = {gap["code"] for gap in response.json()["gaps"]}
        self.assertEqual(codes, response_codes)

    def test_decision_package_endpoint_includes_analysis_layers(self):
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
        self.assertIn("disagreement_map", payload)
        self.assertIn("evidence_gaps", payload)
