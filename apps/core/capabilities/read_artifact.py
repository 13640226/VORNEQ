import logging
from dataclasses import dataclass
from uuid import UUID

from apps.core.models import Artifact
from apps.platform_shell.capabilities.base import BaseCapability, CapabilityContext
from apps.platform_shell.capabilities.errors import CapabilityExecutionError

from .artifact_read_policy import (
    ArtifactReadDenied,
    ArtifactReadPolicyRegistry,
    artifact_read_policy_registry,
)

logger = logging.getLogger(__name__)

# Identical to the invoker's own denial message so every denial path is
# indistinguishable to the caller (no existence disclosure).
NOT_AUTHORIZED_MESSAGE = "The capability domain policy denied this invocation."

# Core-side allowlist: whatever a domain policy releases, only these keys leave.
ALLOWED_METADATA_KEYS = ("title", "tags")


@dataclass(frozen=True)
class ReadArtifactInput:
    artifact_id: UUID


@dataclass(frozen=True)
class ReadArtifactOutput:
    id: UUID
    kind: str
    metadata: dict
    is_active: bool


class ReadArtifactCapability(BaseCapability[ReadArtifactInput, ReadArtifactOutput]):
    """Read-only capability over Core Artifact identity.

    Core resolves the Artifact and delegates every authorization decision to the
    read policy registered by the owning domain for `Artifact.kind`. An Artifact
    with no registered policy is not readable. `Artifact.is_active` is a
    necessary precondition only; it never grants access.
    """

    name = "read_artifact_v1"
    input_schema = ReadArtifactInput
    output_schema = ReadArtifactOutput
    policy_registry: ArtifactReadPolicyRegistry = artifact_read_policy_registry

    def _active_artifact(self, artifact_id):
        return Artifact.objects.filter(pk=artifact_id, is_active=True).first()

    def _policy_for(self, artifact):
        policy_cls = self.policy_registry.get(artifact.kind)
        return None if policy_cls is None else policy_cls()

    def authorize(self, context: CapabilityContext, input_data: ReadArtifactInput) -> bool:
        artifact = self._active_artifact(input_data.artifact_id)
        if artifact is None:
            return False
        policy = self._policy_for(artifact)
        if policy is None:
            logger.info("read_artifact_v1 denied: no read policy for kind=%s", artifact.kind)
            return False
        try:
            return policy.authorize(actor=context.actor, artifact=artifact) is True
        except Exception:
            # Fail closed; the cause stays in internal logs, never in the result.
            logger.exception("read_artifact_v1 policy authorize failed")
            return False

    def execute(
        self,
        context: CapabilityContext,
        input_data: ReadArtifactInput,
    ) -> ReadArtifactOutput:
        artifact = self._active_artifact(input_data.artifact_id)
        policy = None if artifact is None else self._policy_for(artifact)
        if artifact is None or policy is None:
            raise CapabilityExecutionError("not_authorized", NOT_AUTHORIZED_MESSAGE)

        try:
            projection = policy.read(actor=context.actor, artifact=artifact)
        except ArtifactReadDenied:
            raise CapabilityExecutionError("not_authorized", NOT_AUTHORIZED_MESSAGE) from None

        released = projection.metadata
        metadata = {key: released[key] for key in ALLOWED_METADATA_KEYS if key in released}
        return ReadArtifactOutput(
            id=artifact.id,
            kind=artifact.kind,
            metadata=metadata,
            is_active=artifact.is_active,
        )
