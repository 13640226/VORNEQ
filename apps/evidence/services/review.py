"""
Canonical Review service.

ReviewRecord history is the source of truth for review-derived state.
AssessmentSnapshot is only a derived cache.

ReviewRecord history is append-only.
Review timestamps are kept strictly monotonic per reviewed object so that
the canonical ordering never depends on random UUID ordering.
"""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from apps.evidence.domain.states import ReviewStateRegistry
from apps.evidence.models import Claim, ReviewRecord
from apps.evidence.services.snapshot import SnapshotService


class ReviewService:
    """
    Canonical service for review operations.
    """

    @staticmethod
    def _latest_review(target):
        """
        Return the newest ReviewRecord for target.

        Timestamp is authoritative. UUID is retained only as a defensive
        deterministic secondary ordering key; creation itself guarantees
        strictly increasing timestamps for sequential reviews.
        """
        return (
            ReviewRecord.objects
            .for_object(target)
            .order_by("-timestamp", "-id")
            .first()
        )

    @staticmethod
    def get_current_state(target) -> str:
        """
        Return the current review-derived state.

        If the object has no review history, return its registered
        initial state.
        """
        review = ReviewService._latest_review(target)

        if review is not None:
            return review.new_state

        return ReviewStateRegistry.initial_state_for(target)

    @staticmethod
    def get_current_assessment(
        claim: Claim,
    ) -> dict:
        """
        Return the current Claim assessment derived from canonical
        ReviewRecord history.
        """
        if not isinstance(claim, Claim):
            raise TypeError(
                "get_current_assessment requires a Claim"
            )

        review = ReviewService._latest_review(claim)

        if review is None:
            return {
                "state": "unassessed",
                "timestamp": None,
                "reviewer": None,
                "review_record": None,
            }

        return {
            "state": review.new_state,
            "timestamp": review.timestamp,
            "reviewer": review.reviewer_actor,
            "review_record": review,
        }

    @staticmethod
    @transaction.atomic
    def create_review(
        *,
        target,
        new_state: str,
        reviewer_actor: str,
        notes: str = "",
        change_conditions_met: list | None = None,
    ) -> ReviewRecord:
        """
        Append a canonical ReviewRecord.

        For Claim targets, AssessmentSnapshot is refreshed in the same
        transaction.

        Review timestamps are guaranteed to increase monotonically for
        sequential reviews of the same target.
        """

        if getattr(target, "_state", None) is None:
            raise TypeError(
                "Review target must be a Django model instance"
            )

        if target._state.adding:
            raise ValueError(
                "Review target must be persisted before review"
            )

        if (
            not isinstance(reviewer_actor, str)
            or not reviewer_actor.strip()
        ):
            raise ValueError(
                "reviewer_actor must not be empty"
            )

        ReviewStateRegistry.validate_state(
            target,
            new_state,
        )

        # Serialize review creation for this target whenever the database
        # backend supports row-level locks.
        target_model = target.__class__

        locked_target = (
            target_model._default_manager
            .select_for_update()
            .get(pk=target.pk)
        )

        latest_review = ReviewService._latest_review(
            locked_target
        )

        if latest_review is None:
            previous_state = (
                ReviewStateRegistry.initial_state_for(
                    locked_target
                )
            )
        else:
            previous_state = latest_review.new_state

        # timezone.now() can return the same value for two very fast
        # consecutive calls on some platforms. Never allow equal or
        # decreasing timestamps in one object's append-only history.
        review_timestamp = timezone.now()

        if (
            latest_review is not None
            and review_timestamp <= latest_review.timestamp
        ):
            review_timestamp = (
                latest_review.timestamp
                + timedelta(microseconds=1)
            )

        content_type = ContentType.objects.get_for_model(
            locked_target,
            for_concrete_model=False,
        )

        review = ReviewRecord.objects.create(
            content_type=content_type,
            object_id=str(locked_target.pk),
            reviewer_actor=reviewer_actor.strip(),
            previous_state=previous_state,
            new_state=new_state,
            timestamp=review_timestamp,
            notes=notes,
            change_conditions_met=(
                change_conditions_met
                if change_conditions_met is not None
                else []
            ),
        )

        if isinstance(locked_target, Claim):
            SnapshotService.refresh(
                locked_target
            )

        return review