from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import (
    ContextualReputation,
    ContextualReputationEvent,
    QualitySignal,
    ScoringPolicy,
)


@dataclass(frozen=True)
class ScoringResult:
    applied: bool
    reason: str
    reputation: ContextualReputation | None = None
    event: ContextualReputationEvent | None = None
    delta: float = 0.0


def _policy_delta(*, signal: QualitySignal, policy: ScoringPolicy) -> float | None:
    if not signal.is_eligible:
        return None

    if signal.direction == QualitySignal.Direction.INCONCLUSIVE:
        return 0.0

    raw_weight = policy.direction_weights.get(signal.direction)
    if raw_weight is None:
        return None

    try:
        return float(raw_weight) * float(policy.base_weight)
    except (TypeError, ValueError):
        raise ValidationError("ScoringPolicy contains a non-numeric direction weight.")


@transaction.atomic
def apply_scoring_policy(*, signal: QualitySignal, policy: ScoringPolicy) -> ScoringResult:
    """Apply one explicit, versioned scoring policy to one eligible quality signal.

    The verifier associated with the VerificationResult is the reputation target.
    The signal assessor is only the source of the quality assessment.
    """

    if not isinstance(signal, QualitySignal):
        raise TypeError("signal must be a QualitySignal")
    if not isinstance(policy, ScoringPolicy):
        raise TypeError("policy must be a ScoringPolicy")

    result = signal.verification_result
    verifier_id = result.verifier_id
    if verifier_id is None:
        raise ValidationError("VerificationResult must have a verifier before scoring.")

    normalized_domain = slugify(str(signal.domain or "").strip())
    if not normalized_domain:
        raise ValidationError("QualitySignal must have a non-empty domain.")

    if policy.domain != normalized_domain:
        return ScoringResult(applied=False, reason="policy_domain_mismatch")

    if policy.verification_method_id != signal.method_id:
        return ScoringResult(applied=False, reason="policy_method_mismatch")

    if signal.method_id != result.request.method_id:
        return ScoringResult(applied=False, reason="signal_method_mismatch")

    if not signal.is_eligible:
        return ScoringResult(applied=False, reason="signal_not_eligible")

    delta = _policy_delta(signal=signal, policy=policy)
    if delta is None:
        return ScoringResult(applied=False, reason="direction_not_supported_by_policy")
    if delta == 0.0:
        return ScoringResult(applied=False, reason="non_scoring_direction", delta=0.0)

    reputation, _ = ContextualReputation.objects.select_for_update().get_or_create(
        user_id=verifier_id,
        domain=normalized_domain,
        verification_method_id=signal.method_id,
        defaults={
            "actor_role": ContextualReputation.ActorRole.VERIFIER,
            "score": 0.0,
            "sample_count": 0,
        },
    )
    if reputation.actor_role != ContextualReputation.ActorRole.VERIFIER:
        raise ValidationError(
            "Role mismatch: existing projection is not a verifier reputation."
        )

    existing_event = ContextualReputationEvent.objects.filter(
        contextual_reputation=reputation,
        quality_signal=signal,
        scoring_policy=policy,
        event_type=ContextualReputationEvent.EventType.SCORE_APPLIED,
    ).first()
    if existing_event is not None:
        return ScoringResult(
            applied=False,
            reason="already_applied",
            reputation=reputation,
            event=existing_event,
            delta=existing_event.delta or 0.0,
        )

    previous_score_events = ContextualReputationEvent.objects.filter(
        contextual_reputation=reputation,
        event_type=ContextualReputationEvent.EventType.SCORE_APPLIED,
        scoring_policy__isnull=False,
    ).select_related("scoring_policy")

    incompatible = previous_score_events.exclude(scoring_policy__version=policy.version).first()
    if incompatible is not None:
        return ScoringResult(
            applied=False,
            reason="projection_rebuild_required",
            reputation=reputation,
        )

    if not previous_score_events.exists() and reputation.score != 0.0:
        return ScoringResult(
            applied=False,
            reason="projection_rebuild_required",
            reputation=reputation,
        )

    old_score = float(reputation.score)
    new_score = old_score + delta

    event = ContextualReputationEvent.objects.create(
        contextual_reputation=reputation,
        verification_result=result,
        quality_signal=signal,
        scoring_policy=policy,
        event_type=ContextualReputationEvent.EventType.SCORE_APPLIED,
        old_score=old_score,
        delta=delta,
        new_score=new_score,
        metadata={
            "quality_signal_direction": signal.direction,
            "quality_signal_type": signal.signal_type,
            "policy_version": policy.version,
        },
    )

    reputation.score = new_score
    reputation.last_event_at = timezone.now()
    reputation.save(update_fields=["score", "last_event_at", "updated_at"])

    return ScoringResult(
        applied=True,
        reason="score_applied",
        reputation=reputation,
        event=event,
        delta=delta,
    )
