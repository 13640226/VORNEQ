from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Identity, UserIdentity
from apps.documents.models import DocumentAccess
from apps.documents.search_service import DocumentSearchService, SearchError
from apps.documents.services import DocumentService


User = get_user_model()


def bind_identity(user, name):
    identity = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name=name)
    UserIdentity.objects.create(user=user, identity=identity)
    return identity


class DocumentPrivateSearchTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="search-owner")
        self.editor = User.objects.create_user(username="search-editor")
        self.viewer = User.objects.create_user(username="search-viewer")
        self.outsider = User.objects.create_user(username="search-outsider")
        bind_identity(self.owner, "Search Owner")
        bind_identity(self.editor, "Search Editor")
        bind_identity(self.viewer, "Search Viewer")
        bind_identity(self.outsider, "Search Outsider")

        self.document = DocumentService.create_document(
            user=self.owner,
            title="Private architecture notes",
            content="retrieval boundary",
            tags=["private-search"],
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

    def search(self, user, query="architecture"):
        return DocumentSearchService.search(user=user, query=query, page_size=20)

    def test_owner_editor_and_viewer_can_find_document(self):
        for user in (self.owner, self.editor, self.viewer):
            with self.subTest(user=user.username):
                payload = self.search(user)
                self.assertEqual(payload["total"], 1)
                self.assertEqual(payload["results"][0]["key"], f"document:{self.document.pk}")

    def test_outsider_cannot_observe_result_or_count(self):
        payload = self.search(self.outsider)
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["results"], [])

    def test_results_and_total_are_isolated_to_authorized_documents(self):
        other_owner = User.objects.create_user(username="other-owner")
        bind_identity(other_owner, "Other Owner")
        DocumentService.create_document(
            user=other_owner,
            title="Private architecture second",
            content="must not leak",
        )
        payload = self.search(self.owner)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["results"]), 1)

    def test_inactive_document_is_excluded(self):
        DocumentService.deactivate_document(user=self.owner, document_id=self.document.pk)
        payload = self.search(self.owner)
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["results"], [])

    def test_search_matches_content_and_tags(self):
        self.assertEqual(self.search(self.owner, "retrieval")["total"], 1)
        self.assertEqual(self.search(self.owner, "private-search")["total"], 1)

    def test_backend_failure_is_exposed_as_search_error(self):
        with patch("apps.documents.search_service.UnifiedSearch.search", side_effect=RuntimeError("boom")):
            with self.assertRaises(SearchError):
                self.search(self.owner)
