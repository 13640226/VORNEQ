from apps.core.models import Entitlement


def grant_entitlement(user, product, *, expires_at=None, metadata=None):
    entitlement, created = Entitlement.objects.get_or_create(
        user=user,
        product=product,
        defaults={
            "expires_at": expires_at,
            "metadata": metadata or {},
            "is_active": True,
        },
    )
    if not created:
        entitlement.is_active = True
        entitlement.expires_at = expires_at
        entitlement.metadata = metadata or {}
        entitlement.save(
            update_fields=["is_active", "expires_at", "metadata"]
        )
    return entitlement


def revoke_entitlement(user, product):
    Entitlement.objects.filter(user=user, product=product).update(is_active=False)


def has_valid_entitlement(user, product):
    if not getattr(user, "is_authenticated", False):
        return False
    entitlement = Entitlement.objects.filter(user=user, product=product).first()
    return bool(entitlement and entitlement.is_valid())
