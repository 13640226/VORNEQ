from django.core.exceptions import ValidationError

from .models import DocumentAuditLog


class DocumentAuditService:
    """Record and query domain-owned Document audit events."""

    @classmethod
    def record(cls, *, document, actor_identity, event_type, metadata=None):
        metadata = {} if metadata is None else metadata
        if not isinstance(metadata, dict):
            raise ValidationError("Document audit metadata must be an object.")

        event = DocumentAuditLog(
            document=document,
            actor_identity=actor_identity,
            event_type=event_type,
            metadata=metadata,
        )
        event.full_clean()
        event.save()
        return event

    @classmethod
    def history_for_document(cls, *, document):
        return document.audit_log.select_related("actor_identity").all()
