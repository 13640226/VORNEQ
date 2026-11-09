"""DOC-IDENTITY-02 — inactive account / Identity must never act on Documents.

PROPOSED test module (P0_VORNEQ_DOC_IDENTITY_02_CENTRAL_RESOLVER_PATCH_PREPARATION_V1).
Not executed. Matrix IDs N01–N12 and R01–R04 refer to the preparation report.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Artifact, ArtifactBinding, Identity, UserIdentity
from apps.documents.identity_resolver import (
    IdentityNotFoundError,
    IdentityResolver,
    InactiveIdentityError,
)
from apps.documents.models import Document, DocumentAccess, DocumentAuditLog
from apps.documents.search_service import DocumentSearchService
from apps.documents.services import DocumentService
from apps.platform_shell.capabilities import CapabilityContext, CapabilityInvoker


User = get_user_model()


def bind(user, name, *, kind=Identity.Kind.HUMAN):
    identity = Identity.objects.create(kind=kind, display_name=name)
    # objects.create bypasses UserIdentity.clean(): deliberately lets N01 cover
    # legacy/admin bindings to a non-human Identity.
    UserIdentity.objects.create(user=user, identity=identity)
    return identity


def deactivate(identity):
    identity.is_active = False
    identity.save(update_fields=["is_active"])


class InactiveIdentityBase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="ii-owner", password="pass")
        self.editor = User.objects.create_user(username="ii-editor", password="pass")
        self.viewer = User.objects.create_user(username="ii-viewer", password="pass")
        self.other = User.objects.create_user(username="ii-other", password="pass")
        self.owner_identity = bind(self.owner, "II Owner")
        self.editor_identity = bind(self.editor, "II Editor")
        self.viewer_identity = bind(self.viewer, "II Viewer")
        self.other_identity = bind(self.other, "II Other")

        self.document = DocumentService.create_document(
            user=self.owner, title="Inactive identity probe", content="secret-body", tags=["ii"]
        )
        DocumentService.share_document(
            user=self.owner, document_id=self.document.pk,
            collaborator=self.editor, role=DocumentAccess.Role.EDITOR,
        )
        DocumentService.share_document(
            user=self.owner, document_id=self.document.pk,
            collaborator=self.viewer, role=DocumentAccess.Role.VIEWER,
        )
        self.other_document = DocumentService.create_document(
            user=self.other, title="Other private", content="other-body"
        )

    def audit_count(self):
        return DocumentAuditLog.objects.count()


class ResolverContractTests(InactiveIdentityBase):
    # N01
    def test_n01_anonymous_unbound_inactive_user_and_non_human_are_denied(self):
        unbound = User.objects.create_user(username="ii-unbound")
        inactive_user = User.objects.create_user(username="ii-inactive-user")
        bind(inactive_user, "II Inactive User")
        inactive_user.is_active = False
        inactive_user.save(update_fields=["is_active"])
        org_user = User.objects.create_user(username="ii-org")
        bind(org_user, "II Org", kind=Identity.Kind.ORGANIZATION)

        for actor, exc in (
            (None, PermissionDenied),
            (AnonymousUser(), PermissionDenied),
            (object(), PermissionDenied),
            (unbound, IdentityNotFoundError),
            (inactive_user, InactiveIdentityError),
            (org_user, InactiveIdentityError),
        ):
            with self.subTest(actor=repr(actor)), self.assertRaises(exc):
                IdentityResolver.resolve(actor)

    def test_resolver_never_creates_bindings(self):
        unbound = User.objects.create_user(username="ii-unbound-2")
        before = (Identity.objects.count(), UserIdentity.objects.count())
        with self.assertRaises(IdentityNotFoundError):
            IdentityResolver.resolve(unbound)
        self.assertEqual((Identity.objects.count(), UserIdentity.objects.count()), before)

    # R03
    def test_r03_denial_messages_carry_no_identifiers(self):
        unbound = User.objects.create_user(username="ii-unbound-3")
        deactivate(self.viewer_identity)
        for actor in (unbound, self.viewer):
            with self.subTest(actor=actor.username):
                with self.assertRaises(PermissionDenied) as ctx:
                    IdentityResolver.resolve(actor)
                message = str(ctx.exception)
                self.assertNotIn(str(actor.pk), message)
                self.assertNotIn(actor.username, message)


class InactiveOwnerTests(InactiveIdentityBase):
    def setUp(self):
        super().setUp()
        deactivate(self.owner_identity)

    # N02
    def test_n02_inactive_owner_cannot_read_or_mutate(self):
        before = self.audit_count()
        calls = {
            "get_document": lambda: DocumentService.get_document(
                user=self.owner, document_id=self.document.pk),
            "update_document": lambda: DocumentService.update_document(
                user=self.owner, document_id=self.document.pk, title="hijack"),
            "share_document": lambda: DocumentService.share_document(
                user=self.owner, document_id=self.document.pk,
                collaborator=self.other, role=DocumentAccess.Role.VIEWER),
            "revoke_access": lambda: DocumentService.revoke_access(
                user=self.owner, document_id=self.document.pk, collaborator=self.viewer),
            "deactivate_document": lambda: DocumentService.deactivate_document(
                user=self.owner, document_id=self.document.pk),
            "request_deletion": lambda: DocumentService.request_deletion(
                user=self.owner, document_id=self.document.pk),
            "get_audit_history": lambda: DocumentService.get_audit_history(
                user=self.owner, document_id=self.document.pk),
        }
        for name, call in calls.items():
            with self.subTest(path=name), self.assertRaises(PermissionDenied):
                call()
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Inactive identity probe")
        self.assertTrue(self.document.is_active)
        self.assertTrue(
            DocumentAccess.objects.filter(document=self.document, identity=self.viewer_identity).exists()
        )
        self.assertFalse(
            DocumentAccess.objects.filter(document=self.document, identity=self.other_identity).exists()
        )
        self.assertEqual(self.audit_count(), before)

    def test_n02_views_return_403_without_body_leak(self):
        self.client.force_login(self.owner)
        for url in (
            reverse("documents:detail", args=[self.document.pk]),
            reverse("documents:update", args=[self.document.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, "secret-body", status_code=403)

    # N04
    def test_n04_list_documents_denied(self):
        with self.assertRaises(PermissionDenied):
            list(DocumentService.list_documents(user=self.owner))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("documents:list"))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Inactive identity probe", status_code=403)

    # N05
    def test_n05_homepage_and_recently_viewed_do_not_leak(self):
        with self.assertRaises(PermissionDenied):
            DocumentService.personal_home_recent_documents(user=self.owner)
        with self.assertRaises(PermissionDenied):
            DocumentService.personal_home_recently_viewed(user=self.owner)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("platform_shell:personal_home"))
        self.assertNotEqual(response.status_code, 200)
        self.assertNotContains(response, "Inactive identity probe", status_code=response.status_code)

    # N06
    def test_n06_private_search_returns_nothing(self):
        with self.assertRaises(PermissionDenied):
            DocumentSearchService.search(user=self.owner, query="probe")

    # N07
    def test_n07_create_document_denied_without_side_effects(self):
        counts = (Document.objects.count(), Artifact.objects.count(),
                  ArtifactBinding.objects.count(), self.audit_count())
        with self.assertRaises(PermissionDenied):
            DocumentService.create_document(user=self.owner, title="Blocked")
        self.assertEqual(
            (Document.objects.count(), Artifact.objects.count(),
             ArtifactBinding.objects.count(), self.audit_count()),
            counts,
        )

    def test_n07_inactive_owner_create_form_has_no_side_effects(self):
        self.client.force_login(self.owner)
        before = (
            Document.objects.count(),
            Artifact.objects.count(),
            ArtifactBinding.objects.count(),
            self.audit_count(),
        )
        response = self.client.post(
            reverse("documents:create"),
            {"title": "Must not be created", "content": "private data", "tags": ""},
        )
        # Existing form convention renders validation/permission errors as HTTP 200.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identity is unavailable.")
        self.assertEqual(
            (
                Document.objects.count(),
                Artifact.objects.count(),
                ArtifactBinding.objects.count(),
                self.audit_count(),
            ),
            before,
        )


class InactiveCollaboratorTests(InactiveIdentityBase):
    # N03
    def test_n03_inactive_editor_and_viewer_are_denied(self):
        deactivate(self.editor_identity)
        deactivate(self.viewer_identity)
        for actor in (self.editor, self.viewer):
            with self.subTest(actor=actor.username):
                with self.assertRaises(PermissionDenied):
                    DocumentService.get_document(user=actor, document_id=self.document.pk)
                with self.assertRaises(PermissionDenied):
                    list(DocumentService.list_documents(user=actor))
        with self.assertRaises(PermissionDenied):
            DocumentService.update_document(
                user=self.editor, document_id=self.document.pk, content="tamper")
        self.document.refresh_from_db()
        self.assertEqual(self.document.content, "secret-body")

    # N08
    def test_n08_read_artifact_v1_not_authorized(self):
        deactivate(self.viewer_identity)
        artifact_id = ArtifactBinding.objects.get(object_id=str(self.document.pk)).artifact_id
        result = CapabilityInvoker().invoke(
            "read_artifact_v1",
            context=CapabilityContext(actor=self.viewer, request_id="n08"),
            input_data={"artifact_id": artifact_id},
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")

    # R01
    def test_r01_owner_can_still_revoke_inactive_collaborator(self):
        deactivate(self.viewer_identity)
        DocumentService.revoke_access(
            user=self.owner, document_id=self.document.pk, collaborator=self.viewer)
        self.assertFalse(
            DocumentAccess.objects.filter(document=self.document, identity=self.viewer_identity).exists()
        )

    # R02
    def test_r02_cannot_share_with_inactive_collaborator(self):
        deactivate(self.other_identity)
        with self.assertRaises(ValidationError):
            DocumentService.share_document(
                user=self.owner, document_id=self.document.pk,
                collaborator=self.other, role=DocumentAccess.Role.VIEWER)
        self.assertFalse(
            DocumentAccess.objects.filter(document=self.document, identity=self.other_identity).exists()
        )

    def test_r02_share_form_rejects_inactive_target_without_side_effects(self):
        deactivate(self.other_identity)
        self.client.force_login(self.owner)
        before_shares = DocumentAuditLog.objects.filter(
            document=self.document,
            event_type=DocumentAuditLog.EventType.SHARED,
        ).count()
        before_views = DocumentAuditLog.objects.filter(
            document=self.document,
            event_type=DocumentAuditLog.EventType.VIEWED,
        ).count()
        response = self.client.post(
            reverse("documents:share", args=[self.document.pk]),
            {"collaborator": self.other.username, "role": DocumentAccess.Role.VIEWER},
        )
        # The share form returns HTTP 400 for an invalid target.
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "This collaborator cannot receive access.", status_code=400)
        self.assertFalse(
            DocumentAccess.objects.filter(
                document=self.document, identity=self.other_identity
            ).exists()
        )
        self.assertEqual(
            DocumentAuditLog.objects.filter(
                document=self.document,
                event_type=DocumentAuditLog.EventType.SHARED,
            ).count(),
            before_shares,
        )
        # The error form legitimately reloads the owner's document and records
        # one VIEWED event; this is not an unauthorized SHARED audit event.
        self.assertEqual(
            DocumentAuditLog.objects.filter(
                document=self.document,
                event_type=DocumentAuditLog.EventType.VIEWED,
            ).count(),
            before_views + 1,
        )

    def test_r01_revoke_inactive_target_via_http(self):
        deactivate(self.viewer_identity)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("documents:revoke", args=[self.document.pk]),
            {"collaborator": self.viewer.username},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            DocumentAccess.objects.filter(
                document=self.document, identity=self.viewer_identity
            ).exists()
        )

    # R04
    def test_r04_reactivated_identity_regains_existing_access(self):
        deactivate(self.viewer_identity)
        self.viewer_identity.is_active = True
        self.viewer_identity.save(update_fields=["is_active"])
        self.assertEqual(
            DocumentService.get_document(user=self.viewer, document_id=self.document.pk),
            self.document,
        )


class ActiveBehaviourPreservedTests(InactiveIdentityBase):
    # N09
    def test_n09_active_owner_editor_viewer_unchanged(self):
        for actor in (self.owner, self.editor, self.viewer):
            with self.subTest(actor=actor.username):
                self.assertEqual(
                    DocumentService.get_document(user=actor, document_id=self.document.pk),
                    self.document,
                )
                self.assertIn(self.document, DocumentService.list_documents(user=actor))
                self.assertTrue(DocumentService.can_read(user=actor, document=self.document))
        DocumentService.update_document(
            user=self.editor, document_id=self.document.pk, title="Edited")

    # N10
    def test_n10_cross_user_isolation(self):
        with self.assertRaises(PermissionDenied):
            DocumentService.get_document(user=self.viewer, document_id=self.other_document.pk)
        self.assertNotIn(self.other_document, DocumentService.list_documents(user=self.viewer))
        self.assertNotIn(self.document, DocumentService.list_documents(user=self.other))
        page = DocumentSearchService.search(user=self.viewer, query="other-body")
        self.assertEqual(page["total"], 0)

    # N11
    def test_n11_audit_write_failure_is_fail_closed(self):
        with patch(
            "apps.documents.services.DocumentAuditService.record",
            side_effect=RuntimeError("audit store down"),
        ):
            with self.assertRaises(RuntimeError):
                DocumentService.get_document(user=self.viewer, document_id=self.document.pk)


# N12 — SQLite/PostgreSQL parity is not a separate test: the whole module must
# pass unchanged in both official CI jobs (`test` and `test-postgres`).
