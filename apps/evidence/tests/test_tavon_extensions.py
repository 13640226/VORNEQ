from django.test import TestCase

from apps.evidence.models import Claim, EvidenceRelation, EvidenceState
from apps.evidence.services import DecisionPackageService, EvidenceService, RelationService


class TavonEvidenceExtensionTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(
            claim_text="A technical claim",
            scope="pilot",
        )
        self.supporting = EvidenceService.create_with_provenance(
            content="Supporting evidence",
            source_ref="https://example.com/support",
        )
        self.contradicting = EvidenceService.create_with_provenance(
            content="Contradicting evidence",
            source_ref="https://example.com/contradict",
        )

    def test_evidence_state_is_created_and_recomputed(self):
        supporting_relation = RelationService.create(
            claim=self.claim,
            evidence=self.supporting,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        state = EvidenceState.objects.get(claim=self.claim)
        self.assertEqual(state.state, EvidenceState.State.SUPPORTING_ONLY)
        self.assertEqual(state.evidence_count, 1)

        RelationService.create(
            claim=self.claim,
            evidence=self.contradicting,
            relation=EvidenceRelation.RelationType.CONTRADICTS,
        )

        state.refresh_from_db()
        self.assertEqual(state.state, EvidenceState.State.MIXED)
        self.assertEqual(state.supporting_count, 1)
        self.assertEqual(state.contradicting_count, 1)
        self.assertEqual(state.evidence_count, 2)

        RelationService.retire(relation=supporting_relation)
        state.refresh_from_db()
        self.assertEqual(state.state, EvidenceState.State.CONTRADICTING_ONLY)
        self.assertEqual(state.evidence_count, 1)

    def test_decision_package_is_read_only_and_contains_provenance(self):
        RelationService.create(
            claim=self.claim,
            evidence=self.supporting,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            relation_basis="Bench test result",
        )

        package = DecisionPackageService.build(self.claim)

        self.assertEqual(package["claim"]["claim_text"], "A technical claim")
        self.assertEqual(package["evidence_state"]["state"], EvidenceState.State.SUPPORTING_ONLY)
        self.assertEqual(len(package["evidence"]), 1)
        self.assertEqual(package["evidence"][0]["relation"], EvidenceRelation.RelationType.SUPPORTS)
        self.assertEqual(len(package["evidence"][0]["provenance"]), 1)

        markdown = DecisionPackageService.to_markdown(self.claim)
        self.assertIn("# Decision Record: A technical claim", markdown)
        self.assertIn("Supporting evidence", markdown)
        self.assertIn("Bench test result", markdown)
