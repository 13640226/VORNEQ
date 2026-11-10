from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import uuid4

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class CapabilityContext:
    """Explicit invocation context supplied by the platform boundary.

    ``actor`` must be a :class:`~apps.platform_shell.capabilities.actor.BoundActor`;
    the invoker rejects any other value. Build contexts for HTTP requests with
    :meth:`for_request` so the actor always comes from the authenticated session.
    """

    actor: object
    request_id: str
    request: object | None = None

    @classmethod
    def for_request(cls, request, *, request_id: str | None = None) -> "CapabilityContext":
        from .actor import BoundActor

        return cls(
            actor=BoundActor.from_request(request),
            request_id=request_id or uuid4().hex,
            request=request,
        )


class BaseCapability(ABC, Generic[InputT, OutputT]):
    """Base contract for deploy-time reviewed executable capabilities."""

    name: str
    input_schema: type[InputT]
    output_schema: type[OutputT]

    @abstractmethod
    def authorize(self, context: CapabilityContext, input_data: InputT) -> bool:
        raise NotImplementedError

    @abstractmethod
    def execute(self, context: CapabilityContext, input_data: InputT) -> OutputT:
        raise NotImplementedError
