from dataclasses import fields, is_dataclass
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

from .base import CapabilityContext
from .errors import CapabilityExecutionError, CapabilityResult
from .executable_registry import ExecutableCapabilityRegistry, executable_registry


def _matches_type(value: object, annotation: object) -> bool:
    if annotation is Any:
        return True
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return any(_matches_type(value, item) for item in get_args(annotation))
    if origin is list:
        args = get_args(annotation)
        return isinstance(value, list) and (
            not args or all(_matches_type(item, args[0]) for item in value)
        )
    if origin is tuple:
        return isinstance(value, tuple)
    if origin is dict:
        return isinstance(value, dict)
    if origin is not None:
        try:
            return isinstance(value, origin)
        except TypeError:
            return True
    try:
        return isinstance(value, annotation)
    except TypeError:
        return True


def _validate_dataclass_instance(value: object, schema: type, *, label: str) -> None:
    if not is_dataclass(schema):
        raise CapabilityExecutionError(
            "invalid_contract",
            f"{label} schema must be a dataclass type.",
        )
    if not isinstance(value, schema):
        raise CapabilityExecutionError(
            f"invalid_{label}",
            f"{label.capitalize()} must match {schema.__name__}.",
        )
    hints = get_type_hints(schema)
    for field in fields(schema):
        annotation = hints.get(field.name, Any)
        field_value = getattr(value, field.name)
        if not _matches_type(field_value, annotation):
            raise CapabilityExecutionError(
                f"invalid_{label}",
                f"Field '{field.name}' does not match the declared type.",
            )


def _coerce_input(raw_input: object, schema: type) -> object:
    if isinstance(raw_input, schema):
        value = raw_input
    elif isinstance(raw_input, dict):
        try:
            value = schema(**raw_input)
        except (TypeError, ValueError) as exc:
            raise CapabilityExecutionError(
                "invalid_input",
                "Input does not match the capability schema.",
            ) from exc
    else:
        raise CapabilityExecutionError(
            "invalid_input",
            "Input must be a schema instance or mapping.",
        )
    _validate_dataclass_instance(value, schema, label="input")
    return value


class CapabilityInvoker:
    """Synchronous executable-capability boundary with failure isolation."""

    def __init__(
        self,
        registry: ExecutableCapabilityRegistry = executable_registry,
    ) -> None:
        self.registry = registry

    def invoke(
        self,
        name: str,
        *,
        context: CapabilityContext,
        input_data: object,
    ) -> CapabilityResult:
        try:
            capability_cls = self.registry.get(name)
            if capability_cls is None:
                raise CapabilityExecutionError(
                    "unknown_capability",
                    f"Executable capability '{name}' is not registered.",
                )

            capability = capability_cls()
            typed_input = _coerce_input(input_data, capability.input_schema)
            if not capability.authorize(context, typed_input):
                raise CapabilityExecutionError(
                    "not_authorized",
                    "The capability domain policy denied this invocation.",
                )

            output = capability.execute(context, typed_input)
            _validate_dataclass_instance(
                output,
                capability.output_schema,
                label="output",
            )
            return CapabilityResult.ok(output)
        except CapabilityExecutionError as exc:
            return CapabilityResult.fail(
                exc.code,
                exc.message,
                details=exc.details,
            )
        except Exception:
            return CapabilityResult.fail(
                "execution_failed",
                "Capability execution failed.",
            )
