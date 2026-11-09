"""Minimal registration point for domain-owned Artifact read policies.

Core owns the `read_artifact_v1` capability but must not decide who may read a
domain's data (ADR 012). Each owning domain registers one policy per
`Artifact.kind` at app start-up. An Artifact whose kind has no registered
policy is never readable through the capability (fail closed).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ArtifactReadDenied(Exception):
    """Raised by a policy when a read is not permitted.

    Deliberately carries no detail: the public failure contract must not
    disclose whether the underlying object exists.
    """


@dataclass(frozen=True)
class ArtifactReadProjection:
    """Metadata a domain policy releases for one authorized read."""

    metadata: dict


class ArtifactReadPolicy(ABC):
    """Domain-owned read policy for one `Artifact.kind`."""

    kind: str

    @abstractmethod
    def authorize(self, *, actor: object, artifact) -> bool:
        """Return True only if `actor` may read `artifact`. Must not write."""
        raise NotImplementedError

    @abstractmethod
    def read(self, *, actor: object, artifact) -> ArtifactReadProjection:
        """Re-check authorization, perform required audit, release metadata.

        Raises `ArtifactReadDenied` when the read is not permitted. Any other
        exception (for example an audit-write failure) must propagate so that
        no protected data is released.
        """
        raise NotImplementedError


class ArtifactReadPolicyRegistry:
    """Deterministic kind -> policy mapping. One policy per kind, no overrides."""

    def __init__(self) -> None:
        self._policies: dict[str, type[ArtifactReadPolicy]] = {}

    def register(self, policy_cls: type[ArtifactReadPolicy]) -> None:
        if not (isinstance(policy_cls, type) and issubclass(policy_cls, ArtifactReadPolicy)):
            raise TypeError("Artifact read policy must subclass ArtifactReadPolicy.")
        kind = getattr(policy_cls, "kind", None)
        if not isinstance(kind, str) or not kind:
            raise ValueError("Artifact read policy must declare a non-empty string kind.")
        existing = self._policies.get(kind)
        if existing is not None and existing is not policy_cls:
            raise ValueError(f"An Artifact read policy is already registered for kind '{kind}'.")
        self._policies[kind] = policy_cls

    def get(self, kind: str) -> type[ArtifactReadPolicy] | None:
        return self._policies.get(kind)


artifact_read_policy_registry = ArtifactReadPolicyRegistry()
