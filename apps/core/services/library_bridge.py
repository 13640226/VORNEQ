from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import ArtifactIdentityRole, Identity
from apps.core.services.registry import resolve_artifact


def _validate_library_item(library_item):
    if library_item is None or library_item.pk is None:
        raise ValidationError("Library author mapping requires a saved LibraryItem.")
    meta = library_item._meta
    if (meta.app_label, meta.model_name) != ("library", "libraryitem"):
        raise ValidationError("Library author mapping only supports LibraryItem.")


@transaction.atomic
def map_library_author_to_identity(library_item, identity, *, mapped_by=None):
    """Explicitly map a LibraryItem to an existing Identity as its author.

    The legacy ``LibraryItem.author`` string is never inspected, normalized, or
    used to resolve/create an Identity. The caller must supply the Identity.
    """
    _validate_library_item(library_item)

    if identity is None or identity.pk is None:
        raise ValidationError("An existing Identity must be supplied explicitly.")
    if not isinstance(identity, Identity):
        raise ValidationError("identity must be an Identity instance.")
    if not identity.is_active:
        raise ValidationError("Inactive identities cannot receive new author roles.")

    artifact = resolve_artifact(library_item)
    if artifact is None:
        raise ValidationError(
            "LibraryItem must be registered as an Artifact before author mapping."
        )

    existing = ArtifactIdentityRole.objects.filter(
        artifact=artifact,
        identity=identity,
        role=ArtifactIdentityRole.Role.AUTHOR,
    ).first()
    if existing:
        return existing, False

    metadata = {
        "source": "explicit_library_author_bridge",
        "library_item_id": str(library_item.pk),
    }
    if mapped_by is not None and getattr(mapped_by, "pk", None) is not None:
        metadata["mapped_by_user_id"] = str(mapped_by.pk)

    role = ArtifactIdentityRole(
        artifact=artifact,
        identity=identity,
        role=ArtifactIdentityRole.Role.AUTHOR,
        metadata=metadata,
    )
    role.full_clean()
    role.save()
    return role, True


def resolve_library_author_identities(library_item):
    """Return explicitly mapped author identities; never infer from author text."""
    _validate_library_item(library_item)
    artifact = resolve_artifact(library_item)
    if artifact is None:
        return Identity.objects.none()

    return Identity.objects.filter(
        artifact_roles__artifact=artifact,
        artifact_roles__role=ArtifactIdentityRole.Role.AUTHOR,
        is_active=True,
    ).distinct()
