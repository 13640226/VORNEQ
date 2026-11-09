from django.test import SimpleTestCase, TestCase

from apps.core.capabilities.artifact_read_policy import (
    ArtifactReadDenied,
    ArtifactReadPolicy,
    ArtifactReadPolicyRegistry,
    ArtifactReadProjection,
)
from apps.core.capabilities.read_artifact import ReadArtifactCapability, ReadArtifactInput
from apps.core.models import Artifact
from apps.platform_shell.capabilities import (
    CapabilityContext,
    CapabilityInvoker,
    ExecutableCapabilityRegistry,
)
from apps.platform_shell.registry import AppManifest, PlatformRegistry


def build_invoker(capability_cls=ReadArtifactCapability):
    platform_registry = PlatformRegistry()
    platform_registry.register(
        AppManifest(
            slug="discover",
            label="Discover",
            url_name="home",
            capabilities=("read_artifact_v1",),
        )
    )
    executable_registry = ExecutableCapabilityRegistry(platform_registry)
    executable_registry.register(capability_cls)
    return CapabilityInvoker(executable_registry)


class ReadArtifactCapabilityTests(TestCase):
    def setUp(self):
        self.invoker = build_invoker()
        self.context = CapabilityContext(actor=object(), request_id="artifact-test")

    def invoke(self, artifact_id):
        return self.invoker.invoke(
            "read_artifact_v1",
            context=self.context,
            input_data=ReadArtifactInput(artifact_id=artifact_id),
        )

    # SECURITY CORRECTION: this replaces `test_reads_active_artifact`, which
    # asserted that any active Artifact was readable by any caller. Active
    # status is now only a precondition; the owning domain's policy decides.
    # Authenticated, authorized reads are covered in
    # apps/documents/tests/test_artifact_read_policy.py.
    def test_active_artifact_without_registered_policy_is_not_readable(self):
        artifact = Artifact.objects.create(
            kind=Artifact.Kind.OTHER,
            metadata={"source": "test"},
            is_active=True,
        )

        result = self.invoke(artifact.id)

        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertEqual(result.error.code, "not_authorized")

    def test_inactive_artifact_is_not_eligible(self):
        artifact = Artifact.objects.create(is_active=False)

        result = self.invoke(artifact.id)

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")

    def test_missing_artifact_is_not_eligible(self):
        artifact = Artifact.objects.create()
        artifact_id = artifact.id
        artifact.delete()

        result = self.invoke(artifact_id)

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")

    def test_missing_and_unreadable_artifacts_fail_identically(self):
        existing = Artifact.objects.create(kind=Artifact.Kind.OTHER, is_active=True)
        missing = Artifact.objects.create()
        missing_id = missing.id
        missing.delete()

        self.assertEqual(self.invoke(existing.id).error, self.invoke(missing_id).error)

    def test_policy_exception_fails_closed_without_leaking_detail(self):
        class ExplodingPolicy(ArtifactReadPolicy):
            kind = "other"

            def authorize(self, *, actor, artifact):
                raise RuntimeError("internal secret detail")

            def read(self, *, actor, artifact):
                raise AssertionError("read must not run after a failed authorize")

        registry = ArtifactReadPolicyRegistry()
        registry.register(ExplodingPolicy)

        class Capability(ReadArtifactCapability):
            policy_registry = registry

        artifact = Artifact.objects.create(kind=Artifact.Kind.OTHER, is_active=True)
        result = build_invoker(Capability).invoke(
            "read_artifact_v1",
            context=self.context,
            input_data=ReadArtifactInput(artifact_id=artifact.id),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")
        self.assertNotIn("internal secret detail", repr(result))

    def test_core_filters_released_metadata_to_title_and_tags(self):
        class LeakyPolicy(ArtifactReadPolicy):
            kind = "other"

            def authorize(self, *, actor, artifact):
                return True

            def read(self, *, actor, artifact):
                return ArtifactReadProjection(
                    metadata={"title": "t", "tags": ["a"], "content": "body", "secret": "x"}
                )

        registry = ArtifactReadPolicyRegistry()
        registry.register(LeakyPolicy)

        class Capability(ReadArtifactCapability):
            policy_registry = registry

        artifact = Artifact.objects.create(
            kind=Artifact.Kind.OTHER,
            metadata={"unrestricted": "must not appear"},
            is_active=True,
        )
        result = build_invoker(Capability).invoke(
            "read_artifact_v1",
            context=self.context,
            input_data=ReadArtifactInput(artifact_id=artifact.id),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data.metadata, {"title": "t", "tags": ["a"]})

    def test_policy_denial_at_read_time_maps_to_not_authorized(self):
        class RaceyPolicy(ArtifactReadPolicy):
            kind = "other"

            def authorize(self, *, actor, artifact):
                return True

            def read(self, *, actor, artifact):
                raise ArtifactReadDenied

        registry = ArtifactReadPolicyRegistry()
        registry.register(RaceyPolicy)

        class Capability(ReadArtifactCapability):
            policy_registry = registry

        artifact = Artifact.objects.create(kind=Artifact.Kind.OTHER, is_active=True)
        result = build_invoker(Capability).invoke(
            "read_artifact_v1",
            context=self.context,
            input_data=ReadArtifactInput(artifact_id=artifact.id),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")


class ArtifactReadPolicyRegistryTests(SimpleTestCase):
    def make_policy(self, kind):
        class Policy(ArtifactReadPolicy):
            def authorize(self, *, actor, artifact):
                return False

            def read(self, *, actor, artifact):
                raise ArtifactReadDenied

        Policy.kind = kind
        return Policy

    def test_register_and_get(self):
        registry = ArtifactReadPolicyRegistry()
        policy = self.make_policy("document")
        registry.register(policy)
        self.assertIs(registry.get("document"), policy)
        self.assertIsNone(registry.get("product"))

    def test_registering_same_policy_twice_is_idempotent(self):
        registry = ArtifactReadPolicyRegistry()
        policy = self.make_policy("document")
        registry.register(policy)
        registry.register(policy)
        self.assertIs(registry.get("document"), policy)

    def test_second_distinct_policy_for_kind_is_rejected(self):
        registry = ArtifactReadPolicyRegistry()
        registry.register(self.make_policy("document"))
        with self.assertRaises(ValueError):
            registry.register(self.make_policy("document"))

    def test_invalid_registrations_are_rejected(self):
        registry = ArtifactReadPolicyRegistry()
        with self.assertRaises(TypeError):
            registry.register(object)
        with self.assertRaises(ValueError):
            registry.register(self.make_policy(""))
