from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils.text import slugify

from apps.core.models import (
    ContextualReputation,
    ContextualReputationEvent,
    UserIdentity,
)
from apps.verification.models import VerificationRequest, VerificationResult


@transaction.atomic
def record_verification_activity(*, verification_result, domain, metadata=None):
    """Record one idempotent verifier reputation activity event.

    During the staged Identity migration, the legacy ``user`` subject remains
    required. If that user already has a canonical UserIdentity binding, the
    same projection row is dual-written with ``identity`` and the explicit
    ``verifier`` actor role. This service never creates an Identity and never
    infers another actor role.

    A submitted verification outcome remains an assertion, not proof of
    verifier accuracy, so this service does not change reputation score.
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

    user_identity = (
        UserIdentity.objects.select_related("identity")
        .filter(user_id=verification_result.verifier_id)
        .first()
    )
    identity = user_identity.identity if user_identity else None

    defaults = {
        "score": 0.0,
        "sample_count": 0,
        "actor_role": ContextualReputation.ActorRole.VERIFIER,
    }
    if identity is not None:
        defaults["identity"] = identity

    reputation, _ = ContextualReputation.objects.select_for_update().get_or_create(
        user_id=verification_result.verifier_id,
        domain=normalized_domain,
        verification_method=verification_result.request.method,
        defaults=defaults,
    )

    if reputation.actor_role != ContextualReputation.ActorRole.VERIFIER:
        raise ValidationError(
            "Verifier activity cannot be written to a reputation projection "
            "with a different actor role."
        )

    if identity is not None:
        if reputation.identity_id is None:
            ContextualReputation.objects.filter(pk=reputation.pk).update(
                identity=identity,
                actor_role=ContextualReputation.ActorRole.VERIFIER,
            )
            reputation.refresh_from_db()
        elif reputation.identity_id != identity.id:
            raise ValidationError(
                "Resolved UserIdentity conflicts with the reputation projection identity."
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
