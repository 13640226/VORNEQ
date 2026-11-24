"""Provision only on Allauth's persisted email-confirmation event."""
import logging

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed, user_signed_up
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.dispatch import receiver

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.core.services.identity_lifecycle import provision_verified_identity

logger = logging.getLogger(__name__)


def _audit(user_id, suffix, outcome, reason, metadata=None, source="allauth.email_confirmed"):
    return record_audit_event(
        event_name="identity.provisioning." + suffix,
        actor={"type": "system", "identifier": source},
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
    _provision(address, "allauth.email_confirmed")


def _provision(address, source):
    user_id = address.user_id
    try:
        with transaction.atomic():
            _, created = provision_verified_identity(address.user)
            if created:
                _audit(user_id, "succeeded", AuditEvent.Outcome.SUCCEEDED,
                       "VERIFIED_EMAIL", {"created": True}, source=source)
    except PermissionDenied:
        _audit(user_id, "denied", AuditEvent.Outcome.DENIED, "INELIGIBLE_ACCOUNT", {"created": False}, source=source)
        logger.warning("Identity provisioning denied")
    except Exception:
        # Provisioning and success audit have rolled back together.
        logger.error("Identity provisioning failed")
        _audit(user_id, "failed", AuditEvent.Outcome.FAILED, "PROVISIONING_ERROR", {"created": False}, source=source)
        raise PermissionDenied("Identity provisioning unavailable.") from None


@receiver(user_signed_up, dispatch_uid="core.social_verified_identity.v1")
def provision_on_social_signup(sender, request, user, sociallogin=None, **kwargs):
    """Only a completed social signup with persisted verified primary email."""
    if sociallogin is None or user.pk is None:
        return
    account = getattr(sociallogin, "account", None)
    if account is None or account.pk is None or account.user_id != user.pk:
        return
    if not SocialAccount.objects.filter(pk=account.pk, user_id=user.pk).exists():
        return
    address = EmailAddress.objects.filter(user_id=user.pk, verified=True, primary=True).first()
    if address is not None:
        _provision(address, "allauth.social_signup")
