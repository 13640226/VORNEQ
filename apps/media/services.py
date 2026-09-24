from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import ArtifactIdentityRole, Identity
from apps.core.services.registry import register_artifact
from apps.media.models import MediaAsset


@transaction.atomic
def register_media_asset(
    media_asset: MediaAsset,
    creator_identity: Identity,
    *,
    publisher_identity: Identity | None = None,
    created_by=None,
):
    """Register a saved MediaAsset and bind explicit existing identities."""
    if media_asset is None or media_asset.pk is None:
        raise ValidationError("Media registration requires a saved MediaAsset.")
    if creator_identity is None or creator_identity.pk is None:
        raise ValidationError("Creator role assignment requires a saved Identity.")
    if not creator_identity.is_active:
        raise ValidationError("Creator Identity must be active.")
    if publisher_identity is not None and (
        publisher_identity.pk is None or not publisher_identity.is_active
    ):
        raise ValidationError("Publisher Identity must be saved and active.")

    artifact, artifact_created = register_artifact(
        media_asset,
        created_by=created_by,
        metadata={
            "media_domain": "asset",
            "media_type": media_asset.media_type,
        },
    )

    creator_role, creator_role_created = ArtifactIdentityRole.objects.get_or_create(
        artifact=artifact,
        identity=creator_identity,
        role=ArtifactIdentityRole.Role.CREATOR,
        defaults={"is_primary": True},
    )

    publisher_role = None
    publisher_role_created = False
    if publisher_identity is not None:
        publisher_role, publisher_role_created = ArtifactIdentityRole.objects.get_or_create(
            artifact=artifact,
            identity=publisher_identity,
            role=ArtifactIdentityRole.Role.PUBLISHER,
        )

    return {
        "artifact": artifact,
        "artifact_created": artifact_created,
        "creator_role": creator_role,
        "creator_role_created": creator_role_created,
        "publisher_role": publisher_role,
        "publisher_role_created": publisher_role_created,
    }
