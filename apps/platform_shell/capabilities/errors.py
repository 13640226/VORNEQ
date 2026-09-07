from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CapabilityFailure:
    code: str
    message: str
    details: dict[str, object] | None = None


@dataclass(frozen=True)
class CapabilityResult(Generic[T]):
    success: bool
    data: T | None = None
    error: CapabilityFailure | None = None

    @classmethod
    def ok(cls, data: T) -> "CapabilityResult[T]":
        return cls(success=True, data=data)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> "CapabilityResult[T]":
        return cls(
            success=False,
            error=CapabilityFailure(code=code, message=message, details=details),
        )


class CapabilityExecutionError(Exception):
    """Controlled internal error converted to CapabilityResult at the boundary."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
