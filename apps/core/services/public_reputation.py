from django.db.models import Prefetch

from apps.core.models import ContextualReputation, ContextualReputationEvent


def _sample_strength(sample_count):
    """Describe sample depth only. This is not confidence or truth probability."""
    if sample_count < 5:
        return "low"
    if sample_count < 20:
        return "medium"
    return "high"


def _serialize_reputation(rep):
    latest_score_event = next(
        (
            event
            for event in rep._public_score_events
            if event.scoring_policy_id is not None
        ),
        None,
    )
    return {
        "domain": rep.domain,
        "verification_method": {
            "code": rep.verification_method.code,
            "name": rep.verification_method.name,
        },
        "actor_role": rep.actor_role,
        "actor_role_label": rep.get_actor_role_display(),
        "score": rep.score,
        "sample_count": rep.sample_count,
        "last_event_at": rep.last_event_at.isoformat() if rep.last_event_at else None,
        "policy_version": (
            latest_score_event.scoring_policy.version if latest_score_event else None
        ),
        "sample_strength": _sample_strength(rep.sample_count),
        "interpretation_note": (
            "Contextual reputation projection; sample_strength describes sample depth "
            "only and is not a confidence score or truth claim."
        ),
    }


def get_public_reputation(user, *, domain=None, method_code=None):
    """Return a public-safe contextual reputation projection for one user.

    Deliberately excludes QualitySignal records, assessors, Evidence, event deltas,
    old/new score history, and all private provenance details.
    """
    score_events = ContextualReputationEvent.objects.filter(
        event_type=ContextualReputationEvent.EventType.SCORE_APPLIED,
    ).select_related("scoring_policy").order_by("-created_at", "-id")

    qs = (
        ContextualReputation.objects.filter(user=user)
        .select_related("verification_method")
        .prefetch_related(
            Prefetch("events", queryset=score_events, to_attr="_public_score_events")
        )
    )
    if domain:
        qs = qs.filter(domain=domain)
    if method_code:
        qs = qs.filter(verification_method__code=method_code)

    return [_serialize_reputation(rep) for rep in qs]
