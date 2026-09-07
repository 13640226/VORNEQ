from dataclasses import dataclass
from uuid import UUID

from apps.core.models import Artifact
from apps.platform_shell.capabilities.base import BaseCapability, CapabilityContext
from apps.platform_shell.capabilities.errors import CapabilityExecutionError


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
    """Read-only PoC over Core Artifact identity.

    `is_active=True` is a narrow PoC eligibility rule only. It is not a
    publication contract and must not be generalized into platform permission.
    """

    name = "read_artifact_v1"
    input_schema = ReadArtifactInput
    output_schema = ReadArtifactOutput

    def authorize(self, context: CapabilityContext, input_data: ReadArtifactInput) -> bool:
        return Artifact.objects.filter(pk=input_data.artifact_id, is_active=True).exists()

    def execute(
        self,
        context: CapabilityContext,
        input_data: ReadArtifactInput,
    ) -> ReadArtifactOutput:
        try:
            artifact = Artifact.objects.get(pk=input_data.artifact_id, is_active=True)
        except Artifact.DoesNotExist as exc:
            raise CapabilityExecutionError(
                "not_authorized",
                "The artifact is not eligible for this PoC capability.",
            ) from exc

        return ReadArtifactOutput(
            id=artifact.id,
            kind=artifact.kind,
            metadata=artifact.metadata,
            is_active=artifact.is_active,
        )
