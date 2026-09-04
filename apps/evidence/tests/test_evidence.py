from django.test import TestCase

from apps.evidence.domain.digests import evidence_digest
from apps.evidence.models import Evidence, ProvenanceStep
from apps.evidence.services import EvidenceService


class EvidenceServiceTests(TestCase):
    def test_create_with_provenance_creates_evidence_and_initial_step(self):
        evidence = EvidenceService.create_with_provenance(
            content="Canonical evidence content",
            content_type=Evidence.ContentType.TEXT,
            source_type=ProvenanceStep.SourceType.HUMAN,
            source_ref="test-source-1",
            metadata={
                "language": "fa",
            },
        )

        self.assertIsNotNone(evidence.pk)

        self.assertEqual(
            evidence.content,
            "Canonical evidence content",
        )

        self.assertEqual(
            evidence.content_type,
            Evidence.ContentType.TEXT,
        )

        self.assertEqual(
            evidence.integrity_digest,
            evidence_digest(
                content="Canonical evidence content",
                content_type=Evidence.ContentType.TEXT,
            ),
        )

        provenance = evidence.provenance_chain.get()

        self.assertEqual(
            provenance.source_type,
            ProvenanceStep.SourceType.HUMAN,
        )

        self.assertEqual(
            provenance.source_ref,
            "test-source-1",
        )

    def test_digest_is_deterministic(self):
        first = evidence_digest(
            content="same-content",
            content_type=Evidence.ContentType.TEXT,
        )

        second = evidence_digest(
            content="same-content",
            content_type=Evidence.ContentType.TEXT,
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            len(first),
            64,
        )

    def test_metadata_is_not_part_of_integrity_digest(self):
        evidence = EvidenceService.create_with_provenance(
            content="immutable-content",
            content_type=Evidence.ContentType.TEXT,
            source_type=ProvenanceStep.SourceType.SYSTEM,
            source_ref="system-test",
            metadata={
                "version": 1,
            },
        )

        original_digest = evidence.integrity_digest

        EvidenceService.update_metadata(
            evidence=evidence,
            new_metadata={
                "version": 2,
                "note": "updated",
            },
        )

        evidence.refresh_from_db()

        self.assertEqual(
            evidence.metadata,
            {
                "version": 2,
                "note": "updated",
            },
        )

        self.assertEqual(
            evidence.integrity_digest,
            original_digest,
        )

    def test_canonical_content_cannot_be_changed_after_creation(self):
        evidence = EvidenceService.create_with_provenance(
            content="original",
            source_ref="immutability-test",
        )

        evidence.content = "modified"

        with self.assertRaises(RuntimeError):
            evidence.save()

        evidence.refresh_from_db()

        self.assertEqual(
            evidence.content,
            "original",
        )

    def test_content_type_cannot_be_changed_after_creation(self):
        evidence = EvidenceService.create_with_provenance(
            content="original",
            content_type=Evidence.ContentType.TEXT,
            source_ref="content-type-test",
        )

        alternative_types = [
            value
            for value in Evidence.ContentType.values
            if value != Evidence.ContentType.TEXT
        ]

        if not alternative_types:
            self.skipTest(
                "Evidence.ContentType currently has only one value"
            )

        evidence.content_type = alternative_types[0]

        with self.assertRaises(RuntimeError):
            evidence.save()

    def test_integrity_digest_cannot_be_changed_after_creation(self):
        evidence = EvidenceService.create_with_provenance(
            content="canonical",
            source_ref="digest-test",
        )

        evidence.integrity_digest = "0" * 64

        with self.assertRaises(RuntimeError):
            evidence.save()

    def test_observed_at_cannot_be_changed_after_creation(self):
        evidence = EvidenceService.create_with_provenance(
            content="canonical",
            source_ref="observed-at-test",
        )

        original_observed_at = evidence.observed_at

        evidence.observed_at = (
            original_observed_at.replace(
                year=original_observed_at.year - 1
            )
        )

        with self.assertRaises(RuntimeError):
            evidence.save()

    def test_metadata_update_is_allowed(self):
        evidence = EvidenceService.create_with_provenance(
            content="canonical",
            source_ref="metadata-test",
            metadata={
                "a": 1,
            },
        )

        evidence.metadata = {
            "a": 2,
        }

        evidence.save(
            update_fields=["metadata"]
        )

        evidence.refresh_from_db()

        self.assertEqual(
            evidence.metadata,
            {
                "a": 2,
            },
        )

    def test_verify_integrity_returns_true_for_valid_evidence(self):
        evidence = EvidenceService.create_with_provenance(
            content="valid-content",
            source_ref="verify-test",
        )

        self.assertTrue(
            EvidenceService.verify_integrity(
                evidence
            )
        )

    def test_verify_integrity_detects_tampered_instance(self):
        evidence = EvidenceService.create_with_provenance(
            content="valid-content",
            source_ref="tamper-test",
        )

        evidence.content = "tampered-content"

        self.assertFalse(
            EvidenceService.verify_integrity(
                evidence
            )
        )

    def test_empty_content_is_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceService.create_with_provenance(
                content="",
                source_ref="empty-test",
            )

    def test_blank_content_is_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceService.create_with_provenance(
                content="   ",
                source_ref="blank-test",
            )

    def test_empty_source_ref_is_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceService.create_with_provenance(
                content="content",
                source_ref="",
            )

    def test_invalid_content_type_is_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceService.create_with_provenance(
                content="content",
                content_type="invalid-content-type",
                source_ref="invalid-type-test",
            )

    def test_invalid_source_type_is_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceService.create_with_provenance(
                content="content",
                source_type="invalid-source-type",
                source_ref="invalid-source-test",
            )

    def test_metadata_must_be_dictionary(self):
        with self.assertRaises(ValueError):
            EvidenceService.create_with_provenance(
                content="content",
                source_ref="metadata-validation",
                metadata=["invalid"],
            )

    def test_creation_is_atomic_if_provenance_creation_fails(self):
        original_create = ProvenanceStep.objects.create

        def failing_create(*args, **kwargs):
            raise RuntimeError(
                "forced provenance failure"
            )

        ProvenanceStep.objects.create = failing_create

        try:
            with self.assertRaises(RuntimeError):
                EvidenceService.create_with_provenance(
                    content="must rollback",
                    source_ref="atomicity-test",
                )
        finally:
            ProvenanceStep.objects.create = original_create

        self.assertFalse(
            Evidence.objects.filter(
                content="must rollback"
            ).exists()
        )