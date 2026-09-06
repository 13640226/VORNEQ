from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import Entitlement
from apps.core.services.registry import resolve_artifact, resolve_identity_for_user


def _canonical_pair_for_grant(user, product, *, identity=None, artifact=None):
    """Resolve and validate the optional canonical pair without creating registry data."""
    identity_was_explicit = identity is not None
    artifact_was_explicit = artifact is not None
    if identity_was_explicit != artifact_was_explicit:
        raise ValidationError(
            "identity and artifact must be supplied together when provided explicitly."
        )

    expected_identity = resolve_identity_for_user(user)
    expected_artifact = resolve_artifact(product)

    if identity_was_explicit:
        if expected_identity is None or expected_artifact is None:
            raise ValidationError(
                "Canonical references cannot be verified because registry bindings are missing."
            )
        if identity != expected_identity or artifact != expected_artifact:
            raise ValidationError(
                "Canonical entitlement references do not match the legacy registry bindings."
            )
        return identity, artifact

    # Dual-write only when both explicit registry bindings already exist. A partial
    # registry state must not produce a half-populated canonical entitlement pair.
    if expected_identity is not None and expected_artifact is not None:
        return expected_identity, expected_artifact
    return None, None


@transaction.atomic
def grant_entitlement(
    user,
    product,
    *,
    expires_at=None,
    metadata=None,
    identity=None,
    artifact=None,
):
    """Grant by the legacy key and enrich the same row with canonical references."""
    canonical_identity, canonical_artifact = _canonical_pair_for_grant(
        user,
        product,
        identity=identity,
        artifact=artifact,
    )

    entitlement, created = Entitlement.objects.get_or_create(
        user=user,
        product=product,
        defaults={
            "identity": canonical_identity,
            "artifact": canonical_artifact,
            "expires_at": expires_at,
            "metadata": metadata or {},
            "is_active": True,
        },
    )

    if created:
        return entitlement

    if entitlement.identity_id or entitlement.artifact_id:
        if not entitlement.identity_id or not entitlement.artifact_id:
            raise ValidationError("Existing entitlement has an incomplete canonical pair.")
        if canonical_identity is not None and (
            entitlement.identity_id != canonical_identity.pk
            or entitlement.artifact_id != canonical_artifact.pk
        ):
            raise ValidationError(
                "Existing canonical entitlement references conflict with registry bindings."
            )

    entitlement.is_active = True
    entitlement.expires_at = expires_at
    entitlement.metadata = metadata or {}
    update_fields = ["is_active", "expires_at", "metadata"]

    if canonical_identity is not None and entitlement.identity_id is None:
        entitlement.identity = canonical_identity
        entitlement.artifact = canonical_artifact
        update_fields.extend(["identity", "artifact"])

    entitlement.full_clean()
    entitlement.save(update_fields=update_fields)
    return entitlement


def revoke_entitlement(user, product):
    """Revoke by the unchanged legacy key during the migration window."""
    Entitlement.objects.filter(user=user, product=product).update(is_active=False)


def has_valid_entitlement(user, product):
    """Authorize with canonical-first validation and legacy fallback.

    During the migration window ``user`` + ``product`` remain the request key and
    canonical-only rows are intentionally unsupported. If the matched Entitlement
    has canonical references, they must form a complete pair and exactly match the
    registry bindings for the supplied legacy key. Missing or conflicting registry
    state fails closed. A row with no canonical references may still authorize via
    the legacy pair until backfill is complete.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    entitlement = (
        Entitlement.objects.select_related("identity", "artifact")
        .filter(user=user, product=product)
        .first()
    )
    if entitlement is None or not entitlement.is_valid():
        return False

    has_identity = entitlement.identity_id is not None
    has_artifact = entitlement.artifact_id is not None

    # Corrupt or partially migrated canonical state must never fall back silently.
    if has_identity != has_artifact:
        return False

    # Legacy fallback remains valid only while this row has not yet been backfilled.
    if not has_identity:
        return True

    expected_identity = resolve_identity_for_user(user)
    expected_artifact = resolve_artifact(product)
    if expected_identity is None or expected_artifact is None:
        return False

    return (
        entitlement.identity_id == expected_identity.pk
        and entitlement.artifact_id == expected_artifact.pk
    )
