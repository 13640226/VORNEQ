from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.evidence.models import Claim, Critique, EvidenceRelation, EvidenceState
from apps.evidence.services import DecisionPackageService, EvidenceService, RelationService


class TavonEdgeCaseContractTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(
            claim_text="Edge-case contract claim",
            scope="regression",
        )

    def test_claim_without_evidence_derives_no_evidence_state(self):
        values = EvidenceState.derive_values(self.claim)

        self.assertEqual(values["state"], EvidenceState.State.NO_EVIDENCE)
        self.assertEqual(values["supporting_count"], 0)
        self.assertEqual(values["contradicting_count"], 0)
        self.assertEqual(values["neutral_count"], 0)
        self.assertEqual(values["evidence_count"], 0)

    def test_decision_package_without_versions_is_explicitly_unversioned(self):
        package = DecisionPackageService.build(self.claim)
        version = package["knowledge_version"]

        self.assertIsNone(version["current_version"])
        self.assertEqual(version["version_count"], 0)
        self.assertEqual(version["last_change_note"], "")
        self.assertIsNone(version["last_version_at"])

    def test_critique_requires_exactly_one_target_at_model_and_database_layers(self):
        critique = Critique(
            body="No target",
            category=Critique.Category.DATA,
        )
        with self.assertRaises(ValidationError):
            critique.full_clean()

        evidence = EvidenceService.create_with_provenance(
            content="Critique target evidence",
            source_ref="demo://edge/critique",
        )
        relation = RelationService.create(
            claim=self.claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        with self.assertRaises(ValidationError):
            Critique(
                claim=self.claim,
                relation=relation,
                body="Both targets",
                category=Critique.Category.DATA,
            ).full_clean()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Critique.objects.create(
                    claim=self.claim,
                    relation=relation,
                    body="Both targets bypassing model validation",
                    category=Critique.Category.DATA,
                )
