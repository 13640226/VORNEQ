from dataclasses import dataclass

from django.test import SimpleTestCase

from apps.platform_shell.capabilities import (
    BaseCapability,
    CapabilityContext,
    CapabilityInvoker,
    ExecutableCapabilityRegistry,
)
from apps.platform_shell.registry import AppManifest, PlatformRegistry


@dataclass(frozen=True)
class EchoInput:
    value: str


@dataclass(frozen=True)
class EchoOutput:
    value: str


class EchoCapability(BaseCapability[EchoInput, EchoOutput]):
    name = "echo_v1"
    input_schema = EchoInput
    output_schema = EchoOutput

    def authorize(self, context, input_data):
        return True

    def execute(self, context, input_data):
        return EchoOutput(value=input_data.value)


class DeniedCapability(EchoCapability):
    name = "denied_v1"

    def authorize(self, context, input_data):
        return False


class BrokenCapability(EchoCapability):
    name = "broken_v1"

    def execute(self, context, input_data):
        raise RuntimeError("provider detail must not escape")


class ExecutableCapabilityTests(SimpleTestCase):
    def make_registry(self, *capabilities):
        platform_registry = PlatformRegistry()
        platform_registry.register(
            AppManifest(
                slug="test-app",
                label="Test App",
                url_name="home",
                capabilities=tuple(capabilities),
            )
        )
        return ExecutableCapabilityRegistry(platform_registry)

    def test_register_requires_canonical_manifest_declaration(self):
        registry = self.make_registry()

        with self.assertRaisesMessage(ValueError, "not declared"):
            registry.register(EchoCapability)

    def test_registers_declared_provider(self):
        registry = self.make_registry("echo_v1")
        registry.register(EchoCapability)

        self.assertIs(registry.get("echo_v1"), EchoCapability)

    def test_invoker_returns_typed_success_envelope(self):
        registry = self.make_registry("echo_v1")
        registry.register(EchoCapability)
        invoker = CapabilityInvoker(registry)

        result = invoker.invoke(
            "echo_v1",
            context=CapabilityContext(actor=object(), request_id="req-1"),
            input_data={"value": "hello"},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data, EchoOutput(value="hello"))
        self.assertIsNone(result.error)

    def test_invoker_rejects_wrong_typed_input(self):
        registry = self.make_registry("echo_v1")
        registry.register(EchoCapability)

        result = CapabilityInvoker(registry).invoke(
            "echo_v1",
            context=CapabilityContext(actor=object(), request_id="req-2"),
            input_data={"value": 123},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "invalid_input")

    def test_domain_authorization_denial_is_bounded(self):
        registry = self.make_registry("denied_v1")
        registry.register(DeniedCapability)

        result = CapabilityInvoker(registry).invoke(
            "denied_v1",
            context=CapabilityContext(actor=object(), request_id="req-3"),
            input_data=EchoInput(value="hello"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")

    def test_provider_failure_is_isolated(self):
        registry = self.make_registry("broken_v1")
        registry.register(BrokenCapability)

        result = CapabilityInvoker(registry).invoke(
            "broken_v1",
            context=CapabilityContext(actor=object(), request_id="req-4"),
            input_data=EchoInput(value="hello"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "execution_failed")
        self.assertNotIn("provider detail", result.error.message)

    def test_unknown_capability_returns_failure_envelope(self):
        result = CapabilityInvoker(self.make_registry()).invoke(
            "missing_v1",
            context=CapabilityContext(actor=object(), request_id="req-5"),
            input_data={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "unknown_capability")
