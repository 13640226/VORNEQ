from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.evidence.models import ReviewRecord
from apps.verification.models import (
    ALLOWED_ARTIFACT_MODELS,
    VerificationEvidence,
    VerificationRequest,
    VerificationResult,
)


class VerificationAuthorizationError(PermissionError):
    pass


class InvalidVerificationTransition(ValueError):
    pass


class DuplicateActiveVerification(ValueError):
    pass


ACTIVE_STATUSES = {
    VerificationRequest.Status.REQUESTED,
    VerificationRequest.Status.IN_PROGRESS,
}


def _actor_label(user):
    if user is None:
        return "system"
    username = getattr(user, "get_username", lambda: "")()
    return username or str(getattr(user, "pk", "unknown"))


def _require_permission(user, permission):
    if user is None or not getattr(user, "is_authenticated", False):
        raise VerificationAuthorizationError("Authentication is required.")
    if not (getattr(user, "is_staff", False) or user.has_perm(permission)):
        raise VerificationAuthorizationError("User is not authorized for this verification action.")


def _record_transition(request, actor, previous_state, new_state, notes=""):
    ReviewRecord.objects.create(
        content_type=ContentType.objects.get_for_model(request, for_concrete_model=False),
        object_id=str(request.pk),
        reviewer_actor=_actor_label(actor),
        previous_state=previous_state,
        new_state=new_state,
        notes=notes,
    )


def _validate_artifact(artifact):
    content_type = ContentType.objects.get_for_model(artifact, for_concrete_model=False)
    key = (content_type.app_label, content_type.model)
    if key not in ALLOWED_ARTIFACT_MODELS:
        raise ValidationError("Artifact type is not supported by Verification V1.")
    return content_type


@transaction.atomic
def request_verification(*, artifact, claim, method, requested_by, expires_at=None, context=None):
    _require_permission(requested_by, "verification.add_verificationrequest")
    if not method.is_active:
        raise ValidationError("Verification method is inactive.")

    content_type = _validate_artifact(artifact)
    object_id = str(artifact.pk)

    duplicate = VerificationRequest.objects.select_for_update().filter(
        artifact_content_type=content_type,
        artifact_object_id=object_id,
        claim=claim,
        method=method,
        status__in=ACTIVE_STATUSES,
    ).exists()
    if duplicate:
        raise DuplicateActiveVerification("An active verification request already exists for this artifact, claim, and method.")

    verification_request = VerificationRequest(
        artifact_content_type=content_type,
        artifact_object_id=object_id,
        claim=claim,
        method=method,
        requested_by=requested_by,
        expires_at=expires_at,
        context=context or {},
    )
    verification_request.full_clean()
    verification_request.save()
    _record_transition(
        verification_request,
        requested_by,
        "",
        VerificationRequest.Status.REQUESTED,
        "Verification requested.",
    )
    return verification_request


@transaction.atomic
def start_verification(*, verification_request, actor):
    _require_permission(actor, "verification.change_verificationrequest")
    locked = VerificationRequest.objects.select_for_update().get(pk=verification_request.pk)
    if locked.status != VerificationRequest.Status.REQUESTED:
        raise InvalidVerificationTransition(f"Cannot start verification from state {locked.status!r}.")

    previous = locked.status
    locked.status = VerificationRequest.Status.IN_PROGRESS
    locked.save(update_fields=["status", "updated_at"])
    _record_transition(locked, actor, previous, locked.status, "Verification started.")
    return locked


@transaction.atomic
def submit_verification_result(
    *,
    verification_request,
    verifier,
    outcome,
    reported_confidence,
    summary="",
    metadata=None,
    evidence_links=None,
):
    _require_permission(verifier, "verification.add_verificationresult")
    locked = VerificationRequest.objects.select_for_update().get(pk=verification_request.pk)
    if locked.status != VerificationRequest.Status.IN_PROGRESS:
        raise InvalidVerificationTransition(f"Cannot submit result from state {locked.status!r}.")

    result = VerificationResult(
        request=locked,
        verifier=verifier,
        outcome=outcome,
        reported_confidence=reported_confidence,
        summary=summary,
        metadata=metadata or {},
    )
    result.full_clean()
    result.save()

    for item in evidence_links or []:
        if isinstance(item, dict):
            relation = item["evidence_relation"]
            visibility = item.get("visibility", VerificationEvidence.Visibility.PRIVATE)
            notes = item.get("notes", "")
        else:
            relation = item
            visibility = VerificationEvidence.Visibility.PRIVATE
            notes = ""
        link = VerificationEvidence(
            result=result,
            evidence_relation=relation,
            visibility=visibility,
            notes=notes,
        )
        link.full_clean()
        link.save()

    previous = locked.status
    locked.status = VerificationRequest.Status.COMPLETED
    locked.save(update_fields=["status", "updated_at"])
    _record_transition(locked, verifier, previous, locked.status, "Verification result submitted.")
    return result


def _terminal_transition(*, verification_request, actor, new_state, notes=""):
    _require_permission(actor, "verification.change_verificationrequest")
    if new_state not in {VerificationRequest.Status.FAILED, VerificationRequest.Status.CANCELLED}:
        raise ValueError("Unsupported terminal verification state.")

    with transaction.atomic():
        locked = VerificationRequest.objects.select_for_update().get(pk=verification_request.pk)
        if locked.status not in ACTIVE_STATUSES:
            raise InvalidVerificationTransition(f"Cannot transition from terminal state {locked.status!r}.")
        previous = locked.status
        locked.status = new_state
        locked.save(update_fields=["status", "updated_at"])
        _record_transition(locked, actor, previous, locked.status, notes)
        return locked


def cancel_verification(*, verification_request, actor, notes=""):
    return _terminal_transition(
        verification_request=verification_request,
        actor=actor,
        new_state=VerificationRequest.Status.CANCELLED,
        notes=notes or "Verification cancelled.",
    )


def fail_verification(*, verification_request, actor, notes=""):
    return _terminal_transition(
        verification_request=verification_request,
        actor=actor,
        new_state=VerificationRequest.Status.FAILED,
        notes=notes or "Verification failed.",
    )
