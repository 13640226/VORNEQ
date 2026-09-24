from django.db import transaction

from apps.evidence.models import Critique, Dispute
from apps.evidence.services.review import ReviewService


class DisputeService:
    """Policy service for contestation lifecycle transitions."""

    ALLOWED_TRANSITIONS = {
        "open": {"under_review", "withdrawn"},
        "under_review": {"resolved", "rejected", "withdrawn"},
        "resolved": set(),
        "rejected": set(),
        "withdrawn": set(),
    }

    @staticmethod
    @transaction.atomic
    def open_dispute(*, critique: Critique, opened_by=None, reviewer_actor: str = "system") -> Dispute:
        if not isinstance(critique, Critique):
            raise TypeError("open_dispute requires a Critique")
        if critique._state.adding:
            raise ValueError("Critique must be persisted before opening a dispute")
        if critique.parent_id is not None:
            raise ValueError("Dispute must be opened from a top-level Critique")

        dispute = Dispute(critique=critique, opened_by=opened_by)
        dispute.full_clean()
        dispute.save()

        ReviewService.create_review(
            target=dispute,
            new_state="open",
            reviewer_actor=reviewer_actor,
            notes="Dispute opened from critique.",
        )
        return dispute

    @staticmethod
    def get_state(dispute: Dispute) -> str:
        if not isinstance(dispute, Dispute):
            raise TypeError("get_state requires a Dispute")
        return ReviewService.get_current_state(dispute)

    @staticmethod
    @transaction.atomic
    def transition(*, dispute: Dispute, new_state: str, reviewer_actor: str, notes: str = ""):
        if not isinstance(dispute, Dispute):
            raise TypeError("transition requires a Dispute")

        current_state = DisputeService.get_state(dispute)
        allowed = DisputeService.ALLOWED_TRANSITIONS[current_state]
        if new_state not in allowed:
            raise ValueError(f"Invalid dispute transition: {current_state} -> {new_state}")

        return ReviewService.create_review(
            target=dispute,
            new_state=new_state,
            reviewer_actor=reviewer_actor,
            notes=notes,
        )
