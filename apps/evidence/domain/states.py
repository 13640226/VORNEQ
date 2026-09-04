"""
Canonical review-state registry for the Evidence domain.

ADR-001 v1.0 Frozen:
- Claim, Evidence, and EvidenceRelation have independent vocabularies.
- ChangeCondition operational state is NOT managed by ReviewRecord.
- Missing review history resolves to the registered initial state.
"""


class ReviewStateRegistry:
    """
    Versioned vocabulary registry for ReviewRecord state validation.
    """

    VERSION = "v1"

    CLAIM_STATES = frozenset(
        {
            "unassessed",
            "under_review",
            "provisionally_supported",
            "provisionally_contradicted",
            "inconclusive",
        }
    )

    EVIDENCE_STATES = frozenset(
        {
            "unreviewed",
            "accepted_source",
            "disputed_source",
            "superseded",
        }
    )

    RELATION_STATES = frozenset(
        {
            "active",
            "superseded",
        }
    )

    @classmethod
    def _model_classes(cls):
        # Local imports avoid circular-import problems during Django startup.
        from apps.evidence.models import (
            Claim,
            Evidence,
            EvidenceRelation,
        )

        return Claim, Evidence, EvidenceRelation

    @classmethod
    def vocabulary_for(cls, target):
        Claim, Evidence, EvidenceRelation = cls._model_classes()

        if isinstance(target, Claim):
            return cls.CLAIM_STATES

        if isinstance(target, Evidence):
            return cls.EVIDENCE_STATES

        if isinstance(target, EvidenceRelation):
            return cls.RELATION_STATES

        raise ValueError(
            "No ReviewRecord state vocabulary registered for "
            f"{type(target).__name__}"
        )

    @classmethod
    def initial_state_for(cls, target) -> str:
        Claim, Evidence, EvidenceRelation = cls._model_classes()

        if isinstance(target, Claim):
            return "unassessed"

        if isinstance(target, Evidence):
            return "unreviewed"

        if isinstance(target, EvidenceRelation):
            return "active"

        raise ValueError(
            "No initial review state registered for "
            f"{type(target).__name__}"
        )

    @classmethod
    def is_valid_state(cls, target, state: str) -> bool:
        try:
            vocabulary = cls.vocabulary_for(target)
        except ValueError:
            return False

        return state in vocabulary

    @classmethod
    def validate_state(cls, target, state: str) -> None:
        if not cls.is_valid_state(target, state):
            raise ValueError(
                f"Invalid review state {state!r} for "
                f"{type(target).__name__}"
            )