from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from apps.core.capabilities.read_artifact import ReadArtifactCapability, ReadArtifactInput
from apps.core.models import Artifact, ArtifactBinding, Identity, UserIdentity
from apps.documents.artifact_read_policy import READ_ARTIFACT_AUDIT_METADATA
from apps.documents.models import DocumentAccess, DocumentAuditLog
from apps.documents.services import DocumentService
from apps.platform_shell.capabilities import (
    CapabilityContext,
    CapabilityInvoker,
    ExecutableCapabilityRegistry,
)
from apps.platform_shell.registry import AppManifest, PlatformRegistry

User = get_user_model()


def bind_identity(user, display_name):
    identity = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name=display_name)
    UserIdentity.objects.create(user=user, identity=identity)
    return identity


class DocumentArtifactReadPolicyTests(TestCase):
    """Synthetic, isolated data only. No external services."""

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

        self.owner = User.objects.create_user(username="ra-owner")
        self.editor = User.objects.create_user(username="ra-editor")
        self.viewer = User.objects.create_user(username="ra-viewer")
        self.outsider = User.objects.create_user(username="ra-outsider")
        self.no_identity = User.objects.create_user(username="ra-no-identity")
        self.owner_identity = bind_identity(self.owner, "RA Owner")
        bind_identity(self.editor, "RA Editor")
        bind_identity(self.viewer, "RA Viewer")
        bind_identity(self.outsider, "RA Outsider")

        self.document = DocumentService.create_document(
            user=self.owner,
            title="Synthetic title",
            content="SYNTHETIC-BODY-MUST-NOT-LEAK",
            tags=["alpha", "beta"],
        )
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.editor,
            role=DocumentAccess.Role.EDITOR,
        )
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.viewer,
            role=DocumentAccess.Role.VIEWER,
        )
        self.artifact = ArtifactBinding.objects.get(object_id=str(self.document.pk)).artifact

    def read(self, actor, artifact_id=None):
        return self.invoker.invoke(
            "read_artifact_v1",
            context=CapabilityContext(actor=actor, request_id="doc-read-test"),
            input_data=ReadArtifactInput(artifact_id=artifact_id or self.artifact.id),
        )

    def viewed_events(self):
        return self.document.audit_log.filter(event_type=DocumentAuditLog.EventType.VIEWED)

    def assert_denied(self, result):
        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertEqual(result.error.code, "not_authorized")

    # --- authenticated, authorized access -------------------------------

    def test_owner_reads_title_and_tags_only(self):
        result = self.read(self.owner)

        self.assertTrue(result.success)
        self.assertEqual(result.data.id, self.artifact.id)
        self.assertEqual(result.data.kind, Artifact.Kind.DOCUMENT)
        self.assertEqual(result.data.metadata, {"title": "Synthetic title", "tags": ["alpha", "beta"]})
        self.assertNotIn("SYNTHETIC-BODY-MUST-NOT-LEAK", repr(result))

    def test_editor_and_viewer_collaborators_can_read(self):
        for actor in (self.editor, self.viewer):
            with self.subTest(actor=actor.username):
                self.assertTrue(self.read(actor).success)

    def test_metadata_comes_from_canonical_document_not_artifact_metadata(self):
        Artifact.objects.filter(pk=self.artifact.pk).update(
            metadata={"title": "STALE", "tags": ["stale"], "secret": "from-artifact"}
        )

        result = self.read(self.owner)

        self.assertTrue(result.success)
        self.assertEqual(result.data.metadata, {"title": "Synthetic title", "tags": ["alpha", "beta"]})
        self.assertNotIn("from-artifact", repr(result))

    # --- negative authorization ----------------------------------------

    def test_authenticated_user_without_access_is_denied(self):
        self.assert_denied(self.read(self.outsider))

    def test_unauthenticated_actors_are_denied(self):
        for actor in (AnonymousUser(), None, object()):
            with self.subTest(actor=repr(actor)):
                self.assert_denied(self.read(actor))

    def test_authenticated_user_without_canonical_identity_is_denied(self):
        self.assert_denied(self.read(self.no_identity))

    def test_revoked_collaborator_is_denied(self):
        DocumentService.revoke_access(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.viewer,
        )
        self.assert_denied(self.read(self.viewer))

    def test_deactivated_document_is_denied_even_for_owner(self):
        DocumentService.deactivate_document(user=self.owner, document_id=self.document.pk)
        self.assert_denied(self.read(self.owner))

    def test_pending_deletion_document_is_denied_even_for_owner(self):
        DocumentService.request_deletion(user=self.owner, document_id=self.document.pk)
        self.assert_denied(self.read(self.owner))

    def test_document_artifact_without_binding_is_denied(self):
        orphan = Artifact.objects.create(kind=Artifact.Kind.DOCUMENT, is_active=True)
        self.assert_denied(self.read(self.owner, orphan.id))

    # --- non-disclosure -------------------------------------------------

    def test_denial_is_identical_for_inaccessible_and_nonexistent_artifacts(self):
        missing = Artifact.objects.create()
        missing_id = missing.id
        missing.delete()

        inaccessible = self.read(self.outsider)
        nonexistent = self.read(self.outsider, missing_id)

        self.assert_denied(inaccessible)
        self.assert_denied(nonexistent)
        self.assertEqual(inaccessible.error, nonexistent.error)

    # --- audit ----------------------------------------------------------

    def test_successful_read_records_one_bounded_viewed_event(self):
        before = self.viewed_events().count()

        self.assertTrue(self.read(self.viewer).success)

        self.assertEqual(self.viewed_events().count(), before + 1)
        event = self.viewed_events().first()
        self.assertEqual(event.metadata, READ_ARTIFACT_AUDIT_METADATA)
        self.assertEqual(event.actor_identity.user_binding.user, self.viewer)

    def test_denied_read_records_no_audit_event(self):
        before = self.document.audit_log.count()

        self.assert_denied(self.read(self.outsider))
        self.assert_denied(self.read(AnonymousUser()))

        self.assertEqual(self.document.audit_log.count(), before)

    def test_audit_write_failure_releases_no_protected_content(self):
        before = self.viewed_events().count()

        with patch(
            "apps.documents.artifact_read_policy.DocumentAuditService.record",
            side_effect=RuntimeError("audit store unavailable"),
        ):
            result = self.read(self.owner)

        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        rendered = repr(result)
        self.assertNotIn("Synthetic title", rendered)
        self.assertNotIn("alpha", rendered)
        self.assertNotIn("SYNTHETIC-BODY-MUST-NOT-LEAK", rendered)
        self.assertNotIn("audit store unavailable", rendered)
        self.assertEqual(self.viewed_events().count(), before)

    # --- V1.1: public domain read policy ---------------------------------

    def test_public_can_read_enforces_owner_editor_viewer_and_denies_other_actors(self):
        for actor in (self.owner, self.editor, self.viewer):
            with self.subTest(actor=actor.username):
                self.assertIs(DocumentService.can_read(user=actor, document=self.document), True)
        for actor in (self.outsider, self.no_identity, AnonymousUser(), None, object()):
            with self.subTest(actor=repr(actor)):
                self.assertIs(DocumentService.can_read(user=actor, document=self.document), False)

    def test_inactive_owner_identity_cannot_use_capability_or_can_read(self):
        self.owner_identity.is_active = False
        self.owner_identity.save(update_fields=["is_active"])
        self.assertFalse(DocumentService.can_read(user=self.owner, document=self.document))
        before = self.viewed_events().count()
        self.assert_denied(self.read(self.owner))
        self.assertEqual(self.viewed_events().count(), before)

    def test_inactive_viewer_identity_cannot_use_capability(self):
        viewer_identity = UserIdentity.objects.get(user=self.viewer).identity
        viewer_identity.is_active = False
        viewer_identity.save(update_fields=["is_active"])
        before = self.viewed_events().count()
        self.assert_denied(self.read(self.viewer))
        self.assertEqual(self.viewed_events().count(), before)

    # --- V1.1: recent views exclude only capability-generated VIEWED -----

    def test_capability_only_view_stays_in_audit_not_recently_viewed(self):
        self.assertTrue(self.read(self.owner).success)
        self.assertEqual(self.viewed_events().count(), 1)
        self.assertEqual(
            DocumentService.personal_home_recently_viewed(user=self.owner), []
        )
        self.assertEqual(
            self.viewed_events().first().metadata, READ_ARTIFACT_AUDIT_METADATA
        )

    def test_direct_document_view_stays_recently_viewed(self):
        DocumentService.get_document(user=self.owner, document_id=self.document.pk)
        recent = DocumentService.personal_home_recently_viewed(user=self.owner)
        self.assertEqual([d.pk for d in recent], [self.document.pk])
        self.assertEqual(self.viewed_events().first().metadata, {})

    def test_direct_and_capability_views_yield_one_recent_document(self):
        self.assertTrue(self.read(self.owner).success)
        DocumentService.get_document(user=self.owner, document_id=self.document.pk)
        self.assertTrue(self.read(self.owner).success)
        recent = DocumentService.personal_home_recently_viewed(user=self.owner)
        self.assertEqual([d.pk for d in recent], [self.document.pk])
        self.assertEqual(self.viewed_events().count(), 3)

    def test_legacy_view_without_source_key_remains_visible(self):
        from apps.documents.audit_service import DocumentAuditService

        DocumentAuditService.record(
            document=self.document,
            actor_identity=self.owner_identity,
            event_type=DocumentAuditLog.EventType.VIEWED,
            metadata={},
        )
        recent = DocumentService.personal_home_recently_viewed(user=self.owner)
        self.assertEqual([d.pk for d in recent], [self.document.pk])

    def test_recently_viewed_limit_is_not_consumed_by_capability_events(self):
        second = DocumentService.create_document(user=self.owner, title="Second synthetic")
        third = DocumentService.create_document(user=self.owner, title="Third synthetic")
        DocumentService.get_document(user=self.owner, document_id=second.pk)
        DocumentService.get_document(user=self.owner, document_id=third.pk)
        self.assertTrue(self.read(self.owner).success)
        recent = DocumentService.personal_home_recently_viewed(user=self.owner, limit=2)
        self.assertEqual([d.pk for d in recent], [third.pk, second.pk])
