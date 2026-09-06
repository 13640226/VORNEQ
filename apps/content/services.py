from django.core.exceptions import ValidationError
from django.db import transaction

from apps.content.models import Article
from apps.core.models import ArtifactIdentityRole, Identity
from apps.core.services.registry import register_artifact


@transaction.atomic
def register_article_as_artifact(article: Article, author_identity: Identity, *, created_by=None):
    """Register a saved Article and explicitly bind one existing author Identity."""
    if article is None or article.pk is None:
        raise ValidationError("Article registration requires a saved Article.")
    if author_identity is None or author_identity.pk is None:
        raise ValidationError("Author role assignment requires a saved Identity.")
    if not author_identity.is_active:
        raise ValidationError("Author Identity must be active.")

    artifact, artifact_created = register_artifact(
        article,
        created_by=created_by,
        metadata={"content_domain": "article"},
    )

    role, role_created = ArtifactIdentityRole.objects.get_or_create(
        artifact=artifact,
        identity=author_identity,
        role=ArtifactIdentityRole.Role.AUTHOR,
        defaults={
            "is_primary": True,
            "metadata": {"article_id": str(article.pk)},
        },
    )

    return artifact, artifact_created, role, role_created
