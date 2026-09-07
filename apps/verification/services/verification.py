import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import record_audit_event
from apps.evidence.models import ReviewRecord
from apps.verification.models import (
    ALLOWED_ARTIFACT_MODELS,
    VerificationEvidence,
    VerificationRequest,
    VerificationResult,
)


logger = logging.getLogger(__name__)


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


def _audit_actor(user):
    if user is None:
        return {"type": "system", "identifier": "verification"}
    return {"type": "user", "identifier": user.pk}


def _emit_audit_event(**kwargs):
    def emit():
        try:
            record_audit_event(**kwargs)
        except Exception:
            logger.exception("Audit event emission failed for verification operation.")

    transaction.on_commit(emit)


def _require_permission(user, permission):
    if user is None or not getattr(user, "is_authenticated", False):
        raise VerificationAuthorizationError("Authentication is required.")
    if not (getattr(user, "is_staff", False) or user.has_perm(permission)):
        raise VerificationAuthorizationError("User is not authorized for this verification action.")


def _record_transition(
    request,
    actor,
    previous_state,
    new_state,
    notes="",
    *,
    audit_reason_code,
    audit_event_name="verification.request.changed",
):
    ReviewRecord.objects.create(
        content_type=ContentType.objects.get_for_model(request, for_concrete_model=False),
        object_id=str(request.pk),
        reviewer_actor=_actor_label(actor),
        previous_state=previous_state,
        new_state=new_state,
        notes=notes,
    )

    if audit_event_name == "verification.request.created":
        audit_metadata = {
            "new_state": new_state,
            "request_id": request.pk,
        }
        audit_outcome = "created"
    else:
        audit_metadata = {
            "previous_state": previous_state,
            "new_state": new_state,
            "request_id": request.pk,
        }
        audit_outcome = "changed"

    _emit_audit_event(
        event_name=audit_event_name,
        actor=_audit_actor(actor),
        target={"type": "VerificationRequest", "identifier": request.pk},
        outcome=audit_outcome,
        metadata=audit_metadata,
        reason_code=audit_reason_code,
        correlation_id=None,
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
        audit_event_name="verification.request.created",
        audit_reason_code="REQUEST_CREATED",
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
    _record_transition(
        locked,
        actor,
        previous,
        locked.status,
        "Verification started.",
        audit_reason_code="REQUEST_STARTED",
    )
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

    _emit_audit_event(
        event_name="verification.result.recorded",
        actor=_audit_actor(verifier),
        target={"type": "VerificationResult", "identifier": result.pk},
        outcome="succeeded",
        metadata={
            "result_id": result.pk,
            "request_id": locked.pk,
            "outcome": outcome,
        },
        reason_code="RESULT_RECORDED",
        correlation_id=None,
    )

    previous = locked.status
    locked.status = VerificationRequest.Status.COMPLETED
    locked.save(update_fields=["status", "updated_at"])
    _record_transition(
        locked,
        verifier,
        previous,
        locked.status,
        "Verification result submitted.",
        audit_reason_code="REQUEST_COMPLETED",
    )
    return result


def _terminal_transition(
    *,
    verification_request,
    actor,
    new_state,
    notes="",
    audit_reason_code,
):
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
        _record_transition(
            locked,
            actor,
            previous,
            locked.status,
            notes,
            audit_reason_code=audit_reason_code,
        )
        return locked


def cancel_verification(*, verification_request, actor, notes=""):
    return _terminal_transition(
        verification_request=verification_request,
        actor=actor,
        new_state=VerificationRequest.Status.CANCELLED,
        notes=notes or "Verification cancelled.",
        audit_reason_code="REQUEST_CANCELLED",
    )


def fail_verification(*, verification_request, actor, notes=""):
    return _terminal_transition(
        verification_request=verification_request,
        actor=actor,
        new_state=VerificationRequest.Status.FAILED,
        notes=notes or "Verification failed.",
        audit_reason_code="REQUEST_FAILED",
    )
