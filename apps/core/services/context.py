"""Read-only, disclosure-safe orchestration for Inspect Context V1."""

from urllib.parse import unquote, urlparse
from uuid import UUID

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Artifact, ArtifactBinding, ArtifactIdentityRole
from apps.evidence.models import ProvenanceStep
from apps.verification.public import (
    get_public_evidence_projection,
    get_public_verification_summary,
)
from library.models import LibraryItem
from marketplace.models import Product


SUPPORTED_TARGETS = {
    ("marketplace", "product"),
    ("library", "libraryitem"),
}


def _is_public_content(content_object):
    if isinstance(content_object, Product):
        return content_object.is_public
    if isinstance(content_object, LibraryItem):
        return content_object.is_published
    return False


def _artifact_for_content(content_object):
    if content_object is None or content_object.pk is None:
        return None

    target = (
        content_object._meta.app_config.label,
        content_object._meta.model_name,
    )
    if target not in SUPPORTED_TARGETS:
        return None

    return Artifact.objects.filter(
        binding__content_type__app_label=target[0],
        binding__content_type__model=target[1],
        binding__object_id=str(content_object.pk),
        is_active=True,
    ).first()


def _resolve_uuid(value):
    try:
        artifact_id = UUID(value)
    except (TypeError, ValueError, AttributeError):
        return None

    artifact = Artifact.objects.filter(pk=artifact_id, is_active=True).first()
    if artifact is None:
        return None
    try:
        content_object = artifact.binding.content_object
    except ArtifactBinding.DoesNotExist:
        return None
    return artifact if _is_public_content(content_object) else None


def _candidate_slugs(value):
    parsed = urlparse(value)
    if not (parsed.scheme and parsed.netloc):
        return []

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if not parts:
        return []
    if parts[-1] == "read" and len(parts) > 1:
        parts = parts[:-1]
    return list(dict.fromkeys(reversed(parts[-2:])))


def resolve_artifact_from_input(user_input):
    """Resolve URL/text/Artifact UUID to an existing public V1 artifact.

    This function never creates or mutates canonical records.
    """
    value = (user_input or "").strip()[:2000]
    if not value:
        return None

    artifact = _resolve_uuid(value)
    if artifact is not None:
        return artifact

    for slug in _candidate_slugs(value):
        product = Product.objects.filter(
            slug=slug,
            status=Product.STATUS_APPROVED,
            is_published=True,
        ).first()
        if product is not None:
            artifact = _artifact_for_content(product)
            if artifact is not None:
                return artifact

        library_item = LibraryItem.objects.filter(slug=slug, is_published=True).first()
        if library_item is not None:
            artifact = _artifact_for_content(library_item)
            if artifact is not None:
                return artifact

    product = (
        Product.objects.filter(status=Product.STATUS_APPROVED, is_published=True)
        .filter(Q(title__iexact=value) | Q(slug__iexact=value))
        .first()
    )
    if product is None:
        product = Product.objects.filter(
            status=Product.STATUS_APPROVED,
            is_published=True,
            title__icontains=value,
        ).first()
    if product is not None:
        artifact = _artifact_for_content(product)
        if artifact is not None:
            return artifact

    library_item = (
        LibraryItem.objects.filter(is_published=True)
        .filter(
            Q(title__iexact=value)
            | Q(title_en__iexact=value)
            | Q(title_de__iexact=value)
            | Q(slug__iexact=value)
        )
        .first()
    )
    if library_item is None:
        library_item = (
            LibraryItem.objects.filter(is_published=True)
            .filter(
                Q(title__icontains=value)
                | Q(title_en__icontains=value)
                | Q(title_de__icontains=value)
            )
            .first()
        )
    if library_item is not None:
        return _artifact_for_content(library_item)

    return None


def _source_projection(content_object, language):
    if isinstance(content_object, Product):
        return {
            "title": content_object.title,
            "description": content_object.short_description,
            "type": "product",
            "published_at": content_object.published_at,
            "url": content_object.get_absolute_url(),
        }

    language = (language or "en").split("-", 1)[0]
    return {
        "title": content_object.get_title(language),
        "description": content_object.get_short_description(language),
        "type": "libraryitem",
        "published_at": content_object.published_at,
        "url": reverse("library:detail", kwargs={"slug": content_object.slug}),
    }


def _attribution_projection(artifact):
    now = timezone.now()
    roles = (
        ArtifactIdentityRole.objects.filter(
            artifact=artifact,
            identity__is_active=True,
            valid_from__lte=now,
        )
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
        .select_related("identity")
        .order_by("-is_primary", "role", "identity__display_name")
    )
    return [
        {
            "identity_id": str(role.identity_id),
            "display_name": role.identity.display_name,
            "identity_kind": role.identity.kind,
            "role": role.role,
            "role_label": role.get_role_display(),
            "is_primary": role.is_primary,
        }
        for role in roles
    ]


def _public_provenance_projection(evidence_projection):
    evidence_ids = {
        evidence["evidence_id"]
        for claim in evidence_projection["claims"]
        for evidence in claim["evidences"]
    }
    if not evidence_ids:
        return []

    # Public Evidence visibility does not yet define disclosure policy for
    # source_ref, transformation, or note, so V1 deliberately omits them.
    steps = ProvenanceStep.objects.filter(evidence_id__in=evidence_ids).order_by(
        "timestamp", "id"
    )
    return [
        {
            "evidence_id": str(step.evidence_id),
            "source_type": step.source_type,
            "source_type_label": step.get_source_type_display(),
            "timestamp": step.timestamp,
        }
        for step in steps
    ]


def get_context_view(artifact_id, *, language="en"):
    """Compose one public Inspect Context V1 projection."""
    artifact = Artifact.objects.select_related("binding__content_type").get(
        pk=artifact_id,
        is_active=True,
    )
    binding = artifact.binding
    target = (binding.content_type.app_label, binding.content_type.model)
    if target not in SUPPORTED_TARGETS:
        raise LookupError("Artifact type is not supported by Inspect Context V1.")

    content_object = binding.content_object
    if not _is_public_content(content_object):
        raise LookupError("Artifact is not publicly inspectable.")

    artifact_type = target[1]
    evidence = get_public_evidence_projection(content_object, artifact_type)

    return {
        "artifact": artifact,
        "source": _source_projection(content_object, language),
        "attributions": _attribution_projection(artifact),
        "verification": get_public_verification_summary(content_object),
        "evidence": evidence,
        "provenance": _public_provenance_projection(evidence),
    }
