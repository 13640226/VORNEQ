from django.test import TestCase

from apps.core.capabilities.read_artifact import ReadArtifactCapability, ReadArtifactInput
from apps.core.models import Artifact
from apps.platform_shell.capabilities import (
    CapabilityContext,
    CapabilityInvoker,
    ExecutableCapabilityRegistry,
)
from apps.platform_shell.registry import AppManifest, PlatformRegistry


class ReadArtifactCapabilityTests(TestCase):
    def setUp(self):
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
        executable_registry.register(ReadArtifactCapability)
        self.invoker = CapabilityInvoker(executable_registry)
        self.context = CapabilityContext(actor=object(), request_id="artifact-test")

    def test_reads_active_artifact(self):
        artifact = Artifact.objects.create(
            kind=Artifact.Kind.OTHER,
            metadata={"source": "test"},
            is_active=True,
        )

        result = self.invoker.invoke(
            "read_artifact_v1",
            context=self.context,
            input_data=ReadArtifactInput(artifact_id=artifact.id),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data.id, artifact.id)
        self.assertEqual(result.data.kind, Artifact.Kind.OTHER)
        self.assertEqual(result.data.metadata, {"source": "test"})
        self.assertTrue(result.data.is_active)

    def test_inactive_artifact_is_not_eligible(self):
        artifact = Artifact.objects.create(is_active=False)

        result = self.invoker.invoke(
            "read_artifact_v1",
            context=self.context,
            input_data=ReadArtifactInput(artifact_id=artifact.id),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")

    def test_missing_artifact_is_not_eligible(self):
        artifact = Artifact.objects.create()
        artifact_id = artifact.id
        artifact.delete()

        result = self.invoker.invoke(
            "read_artifact_v1",
            context=self.context,
            input_data=ReadArtifactInput(artifact_id=artifact_id),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")
