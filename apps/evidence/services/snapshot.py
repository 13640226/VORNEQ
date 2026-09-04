"""
Canonical AssessmentSnapshot service.

AssessmentSnapshot is a derived cache only.
ReviewRecord history remains the source of truth.

ADR-001 guarantees:
- A Claim without ReviewRecord must not have a snapshot.
- Snapshot state is derived from the latest canonical ReviewRecord.
- Snapshot can always be rebuilt from review history.
- History takes precedence over cached state.
- Snapshot digest is deterministic and versioned.
"""

from django.db import transaction

from apps.evidence.domain.digests import (
    DIGEST_VERSION,
    snapshot_digest,
)
from apps.evidence.models import (
    AssessmentSnapshot,
    Claim,
    ReviewRecord,
)


class SnapshotService:
    """
    Canonical service for AssessmentSnapshot maintenance.
    """

    @staticmethod
    @transaction.atomic
    def refresh(
        claim: Claim,
    ) -> AssessmentSnapshot | None:
        """
        Rebuild the current snapshot for a Claim from ReviewRecord history.

        If the Claim has no ReviewRecord, any existing snapshot is removed
        and None is returned.
        """

        if claim._state.adding:
            raise ValueError(
                "Claim must be persisted before snapshot refresh"
            )

        # Always resolve the newest ReviewRecord explicitly.
        latest_review = (
            ReviewRecord.objects
            .for_object(claim)
            .order_by("-timestamp", "-id")
            .first()
        )

        # ADR-001 I11:
        # Missing history means unassessed, and no snapshot must exist.
        if latest_review is None:
            AssessmentSnapshot.objects.filter(
                claim=claim
            ).delete()

            return None

        digest = snapshot_digest(
            claim_id=claim.pk,
            review_id=latest_review.pk,
            state=latest_review.new_state,
            timestamp=latest_review.timestamp,
            digest_version=DIGEST_VERSION,
        )

        snapshot, _created = (
            AssessmentSnapshot.objects.update_or_create(
                claim=claim,
                defaults={
                    "current_assessment": latest_review.new_state,
                    "snapshot_at": latest_review.timestamp,
                    "derived_from": latest_review,
                    "digest": digest,
                    "digest_version": DIGEST_VERSION,
                },
            )
        )

        return snapshot

    @staticmethod
    @transaction.atomic
    def rebuild(
        claim: Claim,
    ) -> AssessmentSnapshot | None:
        """
        Explicit rebuild operation.

        ReviewRecord history is the sole authoritative input.
        """

        return SnapshotService.refresh(
            claim
        )

    @staticmethod
    def get(
        claim: Claim,
    ) -> AssessmentSnapshot | None:
        """
        Return the current cached snapshot, if one exists.

        This method does not assert that the cache is current.
        Use verify() when cache consistency must be checked.
        """

        try:
            return AssessmentSnapshot.objects.get(
                claim=claim
            )
        except AssessmentSnapshot.DoesNotExist:
            return None

    @staticmethod
    def verify(
        claim: Claim,
    ) -> bool:
        """
        Verify that the existing snapshot matches canonical history.

        Returns:
            True:
                Snapshot is consistent with the latest ReviewRecord,
                or neither history nor snapshot exists.

            False:
                Snapshot is missing, stale, incorrectly derived,
                or has an invalid digest.
        """

        # Always resolve the newest ReviewRecord explicitly.
        latest_review = (
            ReviewRecord.objects
            .for_object(claim)
            .order_by("-timestamp", "-id")
            .first()
        )

        snapshot = SnapshotService.get(
            claim
        )

        # No review history means no snapshot should exist.
        if latest_review is None:
            return snapshot is None

        # Review exists but snapshot is missing.
        if snapshot is None:
            return False

        expected_digest = snapshot_digest(
            claim_id=claim.pk,
            review_id=latest_review.pk,
            state=latest_review.new_state,
            timestamp=latest_review.timestamp,
            digest_version=DIGEST_VERSION,
        )

        return all(
            (
                snapshot.current_assessment
                == latest_review.new_state,

                snapshot.derived_from_id
                == latest_review.pk,

                snapshot.snapshot_at
                == latest_review.timestamp,

                snapshot.digest_version
                == DIGEST_VERSION,

                snapshot.digest
                == expected_digest,
            )
        )