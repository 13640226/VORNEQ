from django import template

from apps.core.services.library_bridge import resolve_library_author_identities
from apps.core.services.registry import resolve_identity_for_user


register = template.Library()


@register.simple_tag
def canonical_identity(user):
    """Return the public-safe canonical Identity projection for a saved user."""
    if user is None or not getattr(user, "pk", None):
        return None

    identity = resolve_identity_for_user(user)
    if identity is None:
        return None

    return {
        "id": str(identity.id),
        "kind": identity.kind,
    }


@register.simple_tag
def library_canonical_identities(library_item):
    """Return public-safe projections for explicitly mapped Library authors."""
    if library_item is None or not getattr(library_item, "pk", None):
        return []

    return [
        {
            "id": str(identity.id),
            "kind": identity.kind,
        }
        for identity in resolve_library_author_identities(library_item)
    ]
