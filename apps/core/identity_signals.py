"""Provision only on Allauth's persisted email-confirmation event."""
import logging

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.dispatch import receiver

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.core.services.identity_lifecycle import provision_verified_identity

logger = logging.getLogger(__name__)


def _audit(user_id, suffix, outcome, reason, metadata=None):
    return record_audit_event(
        event_name="identity.provisioning." + suffix,
        actor={"type": "system", "identifier": "allauth.email_confirmed"},
        target={"type": "User", "identifier": user_id},
        outcome=outcome, reason_code=reason, metadata=metadata,
        retention_class=AuditEvent.RetentionClass.SECURITY,
    )


@receiver(email_confirmed, sender=EmailAddress, dispatch_uid="core.verified_identity.v1")
def provision_on_email_confirmation(sender, request, email_address, **kwargs):
    # Re-read persisted evidence, never trust the request or a stale signal object.
    address = EmailAddress.objects.filter(pk=email_address.pk, user_id=email_address.user_id,
                                          verified=True, primary=True).first()
    if address is None:
        return
    user_id = address.user_id
    try:
        with transaction.atomic():
            _, created = provision_verified_identity(address.user)
            if created:
                _audit(user_id, "succeeded", AuditEvent.Outcome.SUCCEEDED,
                       "VERIFIED_EMAIL", {"created": True})
    except PermissionDenied:
        _audit(user_id, "denied", AuditEvent.Outcome.DENIED, "INELIGIBLE_ACCOUNT", {"created": False})
        logger.warning("Identity provisioning denied")
    except Exception:
        # Provisioning and success audit have rolled back together.
        logger.error("Identity provisioning failed")
        _audit(user_id, "failed", AuditEvent.Outcome.FAILED, "PROVISIONING_ERROR", {"created": False})
        raise PermissionDenied("Identity provisioning unavailable.") from None
