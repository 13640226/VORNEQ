"""Documents-domain read policy for the Core `read_artifact_v1` capability.

Authorization reuses the existing DocumentService role rules (owner, editor,
viewer). Released metadata comes from the canonical Document, never from
`Artifact.metadata`, and is limited to title and tags.
"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.capabilities.artifact_read_policy import (
    ArtifactReadDenied,
    ArtifactReadPolicy,
    ArtifactReadProjection,
)
from apps.core.models import Artifact, ArtifactBinding

from .audit_service import CAPABILITY_READ_AUDIT_SOURCE, DocumentAuditService
from .identity_resolver import IdentityResolver
from .models import Document, DocumentAuditLog
from .services import DocumentService

logger = logging.getLogger(__name__)

# Fixed, bounded marker: never derived from caller input.
READ_ARTIFACT_AUDIT_METADATA = {"source": CAPABILITY_READ_AUDIT_SOURCE}


class DocumentArtifactReadPolicy(ArtifactReadPolicy):
    kind = Artifact.Kind.DOCUMENT.value

    @staticmethod
    def _document_for(artifact):
        content_type = ContentType.objects.get_for_model(Document, for_concrete_model=False)
        try:
            binding = ArtifactBinding.objects.get(artifact=artifact, content_type=content_type)
            return Document.objects.get(pk=binding.object_id, is_active=True)
        except (
            ArtifactBinding.DoesNotExist,
            Document.DoesNotExist,
            ValueError,
            ValidationError,
        ):
            return None

    def authorize(self, *, actor, artifact) -> bool:
        document = self._document_for(artifact)
        if document is None:
            logger.info("read_artifact_v1 denied: no active bound document")
            return False
        allowed = DocumentService.can_read(user=actor, document=document)
        if not allowed:
            logger.info("read_artifact_v1 denied: actor has no read role")
        return allowed

    def read(self, *, actor, artifact) -> ArtifactReadProjection:
        with transaction.atomic():
            document = self._document_for(artifact)
            if document is None or not DocumentService.can_read(user=actor, document=document):
                raise ArtifactReadDenied
            # Audit only a successful authorized read. A failure here propagates
            # and rolls back, so nothing below is ever released.
            DocumentAuditService.record(
                document=document,
                actor_identity=IdentityResolver.resolve(actor),
                event_type=DocumentAuditLog.EventType.VIEWED,
                metadata=dict(READ_ARTIFACT_AUDIT_METADATA),
            )
        return ArtifactReadProjection(
            metadata={"title": document.title, "tags": list(document.tags)}
        )
