from django.core.exceptions import ValidationError

from .models import AuditEvent


EVENT_SCHEMAS = {
    "verification.request.created": {
        "required_keys": {"new_state", "request_id"},
        "allowed_keys": {"new_state": str, "request_id": int},
        "reason_codes": {"REQUEST_CREATED"},
        "outcomes": {AuditEvent.Outcome.CREATED},
    },
    "verification.request.changed": {
        "required_keys": {"previous_state", "new_state", "request_id"},
        "allowed_keys": {
            "previous_state": str,
            "new_state": str,
            "request_id": int,
        },
        "reason_codes": {
            "REQUEST_STARTED",
            "REQUEST_COMPLETED",
            "REQUEST_CANCELLED",
            "REQUEST_FAILED",
        },
        "outcomes": {AuditEvent.Outcome.CHANGED},
    },
    "verification.result.recorded": {
        "required_keys": {"result_id", "request_id", "outcome"},
        "allowed_keys": {"result_id": int, "request_id": int, "outcome": str},
        "reason_codes": {"RESULT_RECORDED"},
        "outcomes": {AuditEvent.Outcome.SUCCEEDED},
    },
}

ACTOR_TYPES = {"user", "system"}
STRUCTURED_REFERENCE_KEYS = {"type", "identifier"}


def _validate_reference(value, *, label, actor=False):
    if not isinstance(value, dict) or set(value) != STRUCTURED_REFERENCE_KEYS:
        raise ValidationError(
            f"{label} must have exactly 'type' and 'identifier' keys."
        )
    if actor and value["type"] not in ACTOR_TYPES:
        raise ValidationError("Actor type must be 'user' or 'system'.")
    if not isinstance(value["type"], str) or not value["type"]:
        raise ValidationError(f"{label} type must be a non-empty string.")
    if not isinstance(value["identifier"], (str, int)):
        raise ValidationError(f"{label} identifier must be a string or integer.")


def record_audit_event(
    *,
    event_name,
    actor,
    target,
    outcome,
    metadata=None,
    reason_code="",
    correlation_id=None,
    retention_class=AuditEvent.RetentionClass.STANDARD,
):
    schema = EVENT_SCHEMAS.get(event_name)
    if schema is None:
        raise ValidationError(f"Unknown event_name: {event_name}")

    _validate_reference(actor, label="Actor", actor=True)
    _validate_reference(target, label="Target")

    if outcome not in schema["outcomes"]:
        raise ValidationError(f"Invalid outcome for {event_name}: {outcome}")
    if reason_code not in schema["reason_codes"]:
        raise ValidationError(f"Invalid reason_code for {event_name}: {reason_code}")

    metadata = {} if metadata is None else metadata
    if not isinstance(metadata, dict):
        raise ValidationError("Audit metadata must be an object.")

    allowed_keys = schema["allowed_keys"]
    if set(metadata) != schema["required_keys"]:
        raise ValidationError(
            f"Audit metadata keys for {event_name} must be exactly "
            f"{sorted(schema['required_keys'])}."
        )
    for key, value in metadata.items():
        expected_type = allowed_keys[key]
        if not isinstance(value, expected_type):
            raise ValidationError(
                f"Metadata key '{key}' expects {expected_type.__name__}."
            )

    event = AuditEvent(
        event_name=event_name,
        actor=actor,
        target=target,
        outcome=outcome,
        reason_code=reason_code,
        correlation_id=correlation_id,
        metadata=metadata,
        retention_class=retention_class,
    )
    event.full_clean()
    event.save()
    return event
