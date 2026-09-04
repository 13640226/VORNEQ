from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.evidence.models import (
    Claim,
    EvidenceRelation,
)
from apps.evidence.services import (
    EvidenceService,
    RelationService,
)


class RelationServiceTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(
            claim_text="Test claim",
            scope="E0 relation tests",
        )

        self.evidence = EvidenceService.create_with_provenance(
            content="Test evidence",
            source_ref="relation-test-source",
        )

    def test_create_active_relation(self):
        relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            relation_basis="Test basis",
        )

        self.assertIsNotNone(relation.pk)

        self.assertEqual(
            relation.claim,
            self.claim,
        )

        self.assertEqual(
            relation.evidence,
            self.evidence,
        )

        self.assertEqual(
            relation.relation,
            EvidenceRelation.RelationType.SUPPORTS,
        )

        self.assertEqual(
            relation.relation_basis,
            "Test basis",
        )

        self.assertIsNone(
            relation.retired_at
        )

        self.assertIsNone(
            relation.supersedes
        )

    def test_get_active_relation_returns_active_relation(self):
        relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        active = RelationService.get_active_relation(
            claim=self.claim,
            evidence=self.evidence,
        )

        self.assertEqual(
            active,
            relation,
        )

    def test_get_active_relation_returns_none_when_missing(self):
        active = RelationService.get_active_relation(
            claim=self.claim,
            evidence=self.evidence,
        )

        self.assertIsNone(active)

    def test_duplicate_active_relation_is_rejected(self):
        RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        with self.assertRaises(ValueError):
            RelationService.create(
                claim=self.claim,
                evidence=self.evidence,
                relation=EvidenceRelation.RelationType.CONTRADICTS,
            )

        self.assertEqual(
            EvidenceRelation.objects.filter(
                claim=self.claim,
                evidence=self.evidence,
                retired_at__isnull=True,
            ).count(),
            1,
        )

    def test_database_constraint_rejects_two_active_relations(self):
        EvidenceRelation.objects.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EvidenceRelation.objects.create(
                    claim=self.claim,
                    evidence=self.evidence,
                    relation=EvidenceRelation.RelationType.CONTRADICTS,
                )

    def test_invalid_relation_type_is_rejected(self):
        with self.assertRaises(ValueError):
            RelationService.create(
                claim=self.claim,
                evidence=self.evidence,
                relation="invalid-relation-type",
            )

    def test_unsaved_claim_is_rejected(self):
        unsaved_claim = Claim(
            claim_text="Unsaved claim",
        )

        with self.assertRaises(ValueError):
            RelationService.create(
                claim=unsaved_claim,
                evidence=self.evidence,
                relation=EvidenceRelation.RelationType.SUPPORTS,
            )

    def test_supersede_retires_old_relation_and_creates_new_relation(self):
        old_relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            relation_basis="Old interpretation",
        )

        new_relation = RelationService.supersede(
            old_relation=old_relation,
            new_relation_type=EvidenceRelation.RelationType.CONTRADICTS,
            new_basis="New interpretation",
        )

        old_relation.refresh_from_db()
        new_relation.refresh_from_db()

        self.assertIsNotNone(
            old_relation.retired_at
        )

        self.assertIsNone(
            new_relation.retired_at
        )

        self.assertEqual(
            new_relation.relation,
            EvidenceRelation.RelationType.CONTRADICTS,
        )

        self.assertEqual(
            new_relation.relation_basis,
            "New interpretation",
        )

        self.assertEqual(
            new_relation.supersedes,
            old_relation,
        )

        self.assertEqual(
            new_relation.claim,
            old_relation.claim,
        )

        self.assertEqual(
            new_relation.evidence,
            old_relation.evidence,
        )

    def test_supersede_preserves_single_active_relation(self):
        old_relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        RelationService.supersede(
            old_relation=old_relation,
            new_relation_type=EvidenceRelation.RelationType.UNCLEAR,
        )

        active_count = EvidenceRelation.objects.filter(
            claim=self.claim,
            evidence=self.evidence,
            retired_at__isnull=True,
        ).count()

        self.assertEqual(
            active_count,
            1,
        )

        total_count = EvidenceRelation.objects.filter(
            claim=self.claim,
            evidence=self.evidence,
        ).count()

        self.assertEqual(
            total_count,
            2,
        )

    def test_cannot_supersede_already_retired_relation(self):
        relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        retired = RelationService.retire(
            relation=relation,
        )

        with self.assertRaises(ValueError):
            RelationService.supersede(
                old_relation=retired,
                new_relation_type=EvidenceRelation.RelationType.CONTRADICTS,
            )

    def test_retire_marks_relation_as_retired(self):
        relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        retired = RelationService.retire(
            relation=relation,
        )

        retired.refresh_from_db()

        self.assertIsNotNone(
            retired.retired_at
        )

        active = RelationService.get_active_relation(
            claim=self.claim,
            evidence=self.evidence,
        )

        self.assertIsNone(active)

    def test_cannot_retire_relation_twice(self):
        relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        retired = RelationService.retire(
            relation=relation,
        )

        with self.assertRaises(ValueError):
            RelationService.retire(
                relation=retired,
            )

    def test_relation_type_is_immutable_after_creation(self):
        relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        relation.relation = (
            EvidenceRelation.RelationType.CONTRADICTS
        )

        with self.assertRaises(RuntimeError):
            relation.save()

        relation.refresh_from_db()

        self.assertEqual(
            relation.relation,
            EvidenceRelation.RelationType.SUPPORTS,
        )

    def test_relation_basis_is_immutable_after_creation(self):
        relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            relation_basis="Original basis",
        )

        relation.relation_basis = "Changed basis"

        with self.assertRaises(RuntimeError):
            relation.save()

        relation.refresh_from_db()

        self.assertEqual(
            relation.relation_basis,
            "Original basis",
        )

    def test_retired_at_is_allowed_to_change(self):
        relation = RelationService.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
        )

        retired = RelationService.retire(
            relation=relation,
        )

        self.assertIsNotNone(
            retired.retired_at
        )