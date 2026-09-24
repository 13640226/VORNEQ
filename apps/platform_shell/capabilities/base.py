from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class CapabilityContext:
    """Explicit invocation context supplied by the platform boundary."""

    actor: object
    request_id: str
    request: object | None = None


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
