"""
Canonical EvidenceRelation application service.

Guarantees:
- At most one active relation exists for each claim/evidence pair.
- Relations are retired instead of destructively replaced.
- Superseding preserves lineage.
- Superseding is atomic.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.evidence.models import Claim, Evidence, EvidenceRelation


class RelationService:
    """
    Canonical service for EvidenceRelation operations.
    """

    @staticmethod
    @transaction.atomic
    def create(
        *,
        claim: Claim,
        evidence: Evidence,
        relation: str,
        relation_basis: str = "",
        created_by=None,
    ) -> EvidenceRelation:
        if claim._state.adding:
            raise ValueError(
                "Claim must be persisted before creating a relation"
            )

        if evidence._state.adding:
            raise ValueError(
                "Evidence must be persisted before creating a relation"
            )

        if relation not in EvidenceRelation.RelationType.values:
            raise ValueError(
                f"Invalid relation type: {relation!r}"
            )

        existing = (
            EvidenceRelation.objects
            .filter(
                claim=claim,
                evidence=evidence,
                retired_at__isnull=True,
            )
            .first()
        )

        if existing is not None:
            raise ValueError(
                "An active relation already exists "
                "for this claim/evidence pair"
            )

        try:
            return EvidenceRelation.objects.create(
                claim=claim,
                evidence=evidence,
                relation=relation,
                relation_basis=relation_basis,
                created_by=created_by,
                retired_at=None,
            )
        except IntegrityError as exc:
            raise ValueError(
                "An active relation already exists "
                "for this claim/evidence pair"
            ) from exc

    @staticmethod
    @transaction.atomic
    def supersede(
        *,
        old_relation: EvidenceRelation,
        new_relation_type: str,
        new_basis: str = "",
        created_by=None,
    ) -> EvidenceRelation:
        if old_relation._state.adding:
            raise ValueError(
                "Relation must be persisted before it can be superseded"
            )

        if new_relation_type not in EvidenceRelation.RelationType.values:
            raise ValueError(
                f"Invalid relation type: {new_relation_type!r}"
            )

        locked = (
            EvidenceRelation.objects
            .select_for_update()
            .get(pk=old_relation.pk)
        )

        if locked.retired_at is not None:
            raise ValueError(
                "Cannot supersede an already retired relation"
            )

        conflicting = (
            EvidenceRelation.objects
            .select_for_update()
            .filter(
                claim=locked.claim,
                evidence=locked.evidence,
                retired_at__isnull=True,
            )
            .exclude(pk=locked.pk)
            .exists()
        )

        if conflicting:
            raise RuntimeError(
                "Multiple active relations detected "
                "for the same claim/evidence pair"
            )

        locked.retired_at = timezone.now()
        locked.save(
            update_fields=["retired_at"]
        )

        try:
            new_relation = EvidenceRelation.objects.create(
                claim=locked.claim,
                evidence=locked.evidence,
                relation=new_relation_type,
                relation_basis=new_basis,
                created_by=created_by,
                supersedes=locked,
                retired_at=None,
            )
        except IntegrityError as exc:
            raise RuntimeError(
                "Failed to create superseding relation"
            ) from exc

        return new_relation

    @staticmethod
    def get_active_relation(
        *,
        claim: Claim,
        evidence: Evidence,
    ) -> EvidenceRelation | None:
        return (
            EvidenceRelation.objects
            .filter(
                claim=claim,
                evidence=evidence,
                retired_at__isnull=True,
            )
            .first()
        )

    @staticmethod
    @transaction.atomic
    def retire(
        *,
        relation: EvidenceRelation,
    ) -> EvidenceRelation:
        if relation._state.adding:
            raise ValueError(
                "Relation must be persisted before it can be retired"
            )

        locked = (
            EvidenceRelation.objects
            .select_for_update()
            .get(pk=relation.pk)
        )

        if locked.retired_at is not None:
            raise ValueError(
                "Relation is already retired"
            )

        locked.retired_at = timezone.now()
        locked.save(
            update_fields=["retired_at"]
        )

        return locked