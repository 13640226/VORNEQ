from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils.text import slugify

from apps.core.models import ContextualReputation, ContextualReputationEvent
from apps.verification.models import VerificationRequest, VerificationResult


@transaction.atomic
def record_verification_activity(*, verification_result, domain, metadata=None):
    """Record one idempotent verification activity event.

    This service deliberately does not change reputation score. A submitted
    outcome is an assertion, not proof of verifier accuracy.
    """

    if not isinstance(verification_result, VerificationResult):
        raise TypeError("verification_result must be a VerificationResult")

    if verification_result.verifier_id is None:
        raise ValidationError("VerificationResult must have a verifier.")

    if verification_result.request.status != VerificationRequest.Status.COMPLETED:
        raise ValidationError(
            "Only results belonging to completed verification requests can be recorded."
        )

    normalized_domain = slugify(str(domain or "").strip())
    if not normalized_domain:
        raise ValidationError("A non-empty reputation domain is required.")

    reputation, _ = ContextualReputation.objects.select_for_update().get_or_create(
        user_id=verification_result.verifier_id,
        domain=normalized_domain,
        verification_method=verification_result.request.method,
        defaults={"score": 0.0, "sample_count": 0},
    )

    event, created = ContextualReputationEvent.objects.get_or_create(
        contextual_reputation=reputation,
        verification_result=verification_result,
        event_type=ContextualReputationEvent.EventType.VERIFICATION_SUBMITTED,
        defaults={"metadata": metadata or {}},
    )

    if created:
        ContextualReputation.objects.filter(pk=reputation.pk).update(
            sample_count=F("sample_count") + 1,
            last_event_at=event.created_at,
        )
        reputation.refresh_from_db()

    return reputation, event, created
