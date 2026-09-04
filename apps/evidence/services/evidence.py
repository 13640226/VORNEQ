"""
Canonical Evidence application service.

This module is the canonical write path for creating Evidence.

Guarantees:
- Evidence is created together with its initial ProvenanceStep.
- integrity_digest is generated internally.
- creation is atomic.
- canonical Evidence fields remain immutable after creation.
- only non-canonical metadata may be updated after creation.
"""

from django.db import transaction
from django.utils import timezone

from apps.evidence.domain.digests import evidence_digest
from apps.evidence.models import Evidence, ProvenanceStep


class EvidenceService:
    """
    Canonical service for Evidence creation and integrity management.
    """

    @staticmethod
    @transaction.atomic
    def create_with_provenance(
        *,
        content: str,
        source_ref: str,
        content_type: str = Evidence.ContentType.TEXT,
        source_type: str = ProvenanceStep.SourceType.HUMAN,
        observed_at=None,
        metadata: dict | None = None,
        created_by=None,
        transformation: str = "",
        note: str = "",
    ) -> Evidence:
        """
        Create Evidence and its initial ProvenanceStep atomically.

        A successfully returned Evidence always has at least one
        provenance step.
        """

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "Evidence content must not be empty"
            )

        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError(
                "Provenance source_ref must not be empty"
            )

        if content_type not in Evidence.ContentType.values:
            raise ValueError(
                f"Invalid Evidence content_type: {content_type!r}"
            )

        if source_type not in ProvenanceStep.SourceType.values:
            raise ValueError(
                f"Invalid Provenance source_type: {source_type!r}"
            )

        if metadata is None:
            metadata = {}

        if not isinstance(metadata, dict):
            raise ValueError(
                "Evidence metadata must be a dictionary"
            )

        if observed_at is None:
            observed_at = timezone.now()

        digest = evidence_digest(
            content=content,
            content_type=content_type,
        )

        evidence = Evidence.objects.create(
            content=content,
            content_type=content_type,
            observed_at=observed_at,
            integrity_digest=digest,
            metadata=metadata,
            created_by=created_by,
        )

        ProvenanceStep.objects.create(
            evidence=evidence,
            source_type=source_type,
            source_ref=source_ref.strip(),
            transformation=transformation,
            timestamp=observed_at,
            note=note,
        )

        return evidence

    @staticmethod
    def get_evidence(
        evidence_id,
    ) -> Evidence | None:
        """
        Return Evidence by primary key, or None if it does not exist.
        """

        try:
            return Evidence.objects.get(
                pk=evidence_id
            )
        except Evidence.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def update_metadata(
        *,
        evidence: Evidence,
        new_metadata: dict,
    ) -> Evidence:
        """
        Replace non-canonical Evidence metadata.

        This is the only supported post-creation mutation in E0.
        """

        if evidence._state.adding:
            raise ValueError(
                "Evidence must be persisted before metadata can be updated"
            )

        if not isinstance(new_metadata, dict):
            raise ValueError(
                "Evidence metadata must be a dictionary"
            )

        evidence.metadata = new_metadata
        evidence.save(
            update_fields=["metadata"]
        )

        return evidence

    @staticmethod
    def verify_integrity(
        evidence: Evidence,
    ) -> bool:
        """
        Recompute the canonical Evidence digest and compare it
        against the stored integrity_digest.
        """

        if evidence._state.adding:
            raise ValueError(
                "Evidence must be persisted before integrity verification"
            )

        expected_digest = evidence_digest(
            content=evidence.content,
            content_type=evidence.content_type,
        )

        return expected_digest == evidence.integrity_digest