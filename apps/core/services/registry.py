from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import Artifact, ArtifactBinding, Identity, UserIdentity


_ARTIFACT_KIND_BY_TARGET = {
    ("marketplace", "product"): Artifact.Kind.PRODUCT,
    ("library", "libraryitem"): Artifact.Kind.LIBRARY_ITEM,
}


def _binding_coordinates(instance):
    """Return the canonical ContentType/object-id pair for a supported object."""
    if instance is None or instance.pk is None:
        raise ValidationError("Artifact registration requires a saved model instance.")

    content_type = ContentType.objects.get_for_model(
        instance,
        for_concrete_model=False,
    )
    target = (content_type.app_label, content_type.model)
    if target not in ArtifactBinding.ALLOWED_TARGETS:
        raise ValidationError("Unsupported artifact registration target.")
    return content_type, str(instance.pk), target


def resolve_artifact(instance):
    """Resolve an already-registered vertical object to its canonical Artifact."""
    content_type, object_id, _ = _binding_coordinates(instance)
    binding = (
        ArtifactBinding.objects.select_related("artifact")
        .filter(content_type=content_type, object_id=object_id)
        .first()
    )
    return binding.artifact if binding else None


@transaction.atomic
def register_artifact(instance, *, created_by=None, metadata=None):
    """Idempotently register a supported vertical object as an Artifact.

    Registration creates registry identity only. It does not infer or assign any
    ArtifactIdentityRole and does not change the vertical object.
    """
    content_type, object_id, target = _binding_coordinates(instance)
    existing = (
        ArtifactBinding.objects.select_related("artifact")
        .filter(content_type=content_type, object_id=object_id)
        .first()
    )
    if existing:
        return existing.artifact, False

    artifact = Artifact.objects.create(
        kind=_ARTIFACT_KIND_BY_TARGET.get(target, Artifact.Kind.OTHER),
        metadata=metadata or {},
    )
    binding = ArtifactBinding(
        artifact=artifact,
        content_type=content_type,
        object_id=object_id,
        created_by=created_by,
    )
    binding.full_clean()
    binding.save()
    return artifact, True


def resolve_identity_for_user(user):
    """Resolve a Django user to an existing canonical human Identity."""
    if user is None or user.pk is None:
        raise ValidationError("Identity resolution requires a saved user.")
    binding = UserIdentity.objects.select_related("identity").filter(user=user).first()
    return binding.identity if binding else None


def _user_display_name(user):
    get_full_name = getattr(user, "get_full_name", None)
    full_name = get_full_name().strip() if callable(get_full_name) else ""
    if full_name:
        return full_name[:200]
    username = getattr(user, "get_username", lambda: "")()
    if username:
        return str(username)[:200]
    return f"user:{user.pk}"


@transaction.atomic
def register_user_identity(user, *, metadata=None):
    """Idempotently bind a Django user to a canonical human Identity."""
    if user is None or user.pk is None:
        raise ValidationError("Identity registration requires a saved user.")

    existing = UserIdentity.objects.select_related("identity").filter(user=user).first()
    if existing:
        return existing.identity, False

    identity = Identity.objects.create(
        kind=Identity.Kind.HUMAN,
        display_name=_user_display_name(user),
        metadata=metadata or {},
    )
    binding = UserIdentity(user=user, identity=identity)
    binding.full_clean()
    binding.save()
    return identity, True
