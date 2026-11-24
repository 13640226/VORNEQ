"""Explicit account provisioning; never invoked by read-only resolution."""
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core.models import Identity
from apps.core.services.registry import register_user_identity, resolve_identity_for_user


@transaction.atomic
def provision_verified_identity(user):
    """Provision only an active account with a verified primary email.

    Callers must independently authorize the provisioning operation.
    Existing inactive identities are never replaced or reactivated.
    """
    if user is None or user.pk is None:
        raise PermissionDenied("Identity provisioning unavailable.")
    account = get_user_model().objects.select_for_update().filter(pk=user.pk).first()
    if account is None or not account.is_active:
        raise PermissionDenied("Identity provisioning unavailable.")
    existing = resolve_identity_for_user(account)
    if existing is not None and (not existing.is_active or existing.kind != Identity.Kind.HUMAN):
        raise PermissionDenied("Identity provisioning unavailable.")
    if not account.email or not EmailAddress.objects.select_for_update().filter(user=account, primary=True, verified=True, email__iexact=account.email).exists():
        raise PermissionDenied("Identity provisioning unavailable.")
    return register_user_identity(account)
