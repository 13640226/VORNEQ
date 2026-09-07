from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Identity, UserIdentity
from apps.documents.models import DocumentAccess
from apps.documents.services import DocumentService
from apps.platform_shell.registry import registry


User = get_user_model()


def bind_identity(user, display_name):
    identity = Identity.objects.create(
        kind=Identity.Kind.HUMAN,
        display_name=display_name,
    )
    UserIdentity.objects.create(user=user, identity=identity)
    return identity


class DocumentWorkspaceViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="ui-owner", password="pass")
        self.editor = User.objects.create_user(username="ui-editor", password="pass")
        self.viewer = User.objects.create_user(username="ui-viewer", password="pass")
        self.outsider = User.objects.create_user(username="ui-outsider", password="pass")
        self.owner_identity = bind_identity(self.owner, "UI Owner")
        self.editor_identity = bind_identity(self.editor, "UI Editor")
        self.viewer_identity = bind_identity(self.viewer, "UI Viewer")
        bind_identity(self.outsider, "UI Outsider")
        self.document = DocumentService.create_document(
            user=self.owner,
            title="Workspace document",
            content="Private content",
            tags=["workspace"],
        )

    def test_manifest_exposes_documents_as_authenticated_workspace_app(self):
        manifest = registry.get("documents")
        self.assertIsNotNone(manifest)
        self.assertTrue(manifest.show_in_primary_nav)
        self.assertTrue(manifest.requires_authentication)
        self.assertEqual(manifest.urlconf, "apps.documents.urls")
        self.assertEqual(manifest.route_prefix, "documents/")
        self.assertEqual(manifest.active_namespaces, ("documents",))

    def test_list_requires_login_and_shows_authorized_document(self):
        response = self.client.get(reverse("documents:list"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.owner)
        response = self.client.get(reverse("documents:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workspace document")

    def test_create_and_update_use_document_service_boundary(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("documents:create"),
            {"title": "Created in UI", "content": "Body", "tags": "one, two"},
        )
        self.assertEqual(response.status_code, 302)
        created = DocumentService.list_documents(user=self.owner).get(title="Created in UI")
        self.assertEqual(created.tags, ["one", "two"])

        response = self.client.post(
            reverse("documents:update", kwargs={"document_id": created.pk}),
            {"title": "Updated in UI", "content": "Body 2", "tags": "two"},
        )
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.title, "Updated in UI")

    def test_outsider_cannot_open_document_detail(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("documents:detail", kwargs={"document_id": self.document.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Private content", status_code=403)

    def test_owner_can_share_and_revoke_from_ui(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("documents:share", kwargs={"document_id": self.document.pk}),
            {"collaborator": self.viewer.username, "role": DocumentAccess.Role.VIEWER},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            DocumentAccess.objects.filter(
                document=self.document,
                identity=self.viewer_identity,
                role=DocumentAccess.Role.VIEWER,
            ).exists()
        )

        response = self.client.post(
            reverse("documents:revoke", kwargs={"document_id": self.document.pk}),
            {"collaborator": self.viewer.username},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            DocumentAccess.objects.filter(
                document=self.document,
                identity=self.viewer_identity,
            ).exists()
        )

    def test_non_owner_cannot_share_from_ui(self):
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.editor,
            role=DocumentAccess.Role.EDITOR,
        )
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("documents:share", kwargs={"document_id": self.document.pk}),
            {"collaborator": self.viewer.username, "role": DocumentAccess.Role.VIEWER},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            DocumentAccess.objects.filter(
                document=self.document,
                identity=self.viewer_identity,
            ).exists()
        )
