import hashlib

from django.test import TestCase

from apps.evidence.models import Claim, Evidence, EvidenceRelation, EvidenceState
from apps.evidence.services import EvidenceService, RelationService

from .analysis import EvidenceGapFinderService


class EvidenceGapFinderEdgeCaseTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(
            claim_text="Gap finder edge-case claim",
            scope="regression",
        )

    @staticmethod
    def _codes(result):
        return {gap["code"] for gap in result["gaps"]}

    def test_missing_provenance_is_reported(self):
        content = "Evidence intentionally created without provenance."
        evidence = Evidence.objects.create(
            content=content,
            content_type=Evidence.ContentType.TEXT,
            integrity_digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
        RelationService.create(
            claim=self.claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        codes = self._codes(EvidenceGapFinderService.build(self.claim))

        self.assertIn("missing_provenance", codes)

    def test_contextual_and_unclear_only_are_neutral_but_still_one_sided(self):
        contextual = EvidenceService.create_with_provenance(
            content="Contextual evidence",
            source_ref="demo://edge/contextual",
        )
        unclear = EvidenceService.create_with_provenance(
            content="Unclear evidence",
            source_ref="demo://edge/unclear",
        )
        RelationService.create(
            claim=self.claim,
            evidence=contextual,
            relation=EvidenceRelation.RelationType.CONTEXTUALIZES,
        )
        RelationService.create(
            claim=self.claim,
            evidence=unclear,
            relation=EvidenceRelation.RelationType.UNCLEAR,
        )

        result = EvidenceGapFinderService.build(self.claim)
        codes = self._codes(result)

        self.assertEqual(result["evidence_state"]["state"], EvidenceState.State.NEUTRAL_ONLY)
        self.assertEqual(result["evidence_state"]["neutral_count"], 2)
        self.assertIn("no_supporting_evidence", codes)
        self.assertIn("no_contradicting_evidence", codes)
        self.assertNotIn("no_evidence", codes)
        self.assertNotIn("missing_provenance", codes)
