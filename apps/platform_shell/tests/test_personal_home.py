from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Identity, UserIdentity
from apps.documents.models import DocumentAccess
from apps.documents.services import DocumentService


User = get_user_model()


def bind_identity(user, display_name):
    identity = Identity.objects.create(
        kind=Identity.Kind.HUMAN,
        display_name=display_name,
    )
    UserIdentity.objects.create(user=user, identity=identity)
    return identity


class PersonalHomeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="personal-home-user")
        self.other = User.objects.create_user(username="personal-home-other")
        bind_identity(self.user, "Personal Home User")
        bind_identity(self.other, "Personal Home Other")
        self.client.force_login(self.user)

    def test_personal_home_requires_login(self):
        self.client.logout()
        home_url = reverse("platform_shell:personal_home")
        login_url = reverse("account_login")
        response = self.client.get(home_url)
        self.assertRedirects(response, f"{login_url}?next={home_url}")

    def test_recent_documents_are_currently_readable_and_creation_ordered(self):
        older = DocumentService.create_document(user=self.user, title="Older readable")
        newer = DocumentService.create_document(user=self.user, title="Newer readable")
        hidden = DocumentService.create_document(user=self.other, title="Other private")

        response = self.client.get(reverse("platform_shell:personal_home"))

        self.assertEqual(response.status_code, 200)
        recent = list(response.context["recent_documents"])
        self.assertEqual([document.pk for document in recent[:2]], [newer.pk, older.pk])
        self.assertNotIn(hidden, recent)
        self.assertContains(response, "Newer readable")
        self.assertNotContains(response, "Other private")

    def test_recent_documents_include_shared_documents(self):
        shared = DocumentService.create_document(user=self.other, title="Shared with me")
        DocumentService.share_document(
            user=self.other,
            document_id=shared.pk,
            collaborator=self.user,
            role=DocumentAccess.Role.VIEWER,
        )

        response = self.client.get(reverse("platform_shell:personal_home"))

        self.assertContains(response, "Shared with me")
        self.assertIn(shared, response.context["recent_documents"])

    def test_recently_viewed_is_deduplicated_and_latest_view_ordered(self):
        first = DocumentService.create_document(user=self.user, title="First viewed")
        second = DocumentService.create_document(user=self.user, title="Second viewed")
        DocumentService.get_document(user=self.user, document_id=first.pk)
        DocumentService.get_document(user=self.user, document_id=second.pk)
        DocumentService.get_document(user=self.user, document_id=first.pk)

        response = self.client.get(reverse("platform_shell:personal_home"))

        viewed = response.context["recently_viewed_documents"]
        self.assertEqual([document.pk for document in viewed], [first.pk, second.pk])

    def test_recently_viewed_excludes_access_that_was_revoked(self):
        shared = DocumentService.create_document(user=self.other, title="Revoked document")
        DocumentService.share_document(
            user=self.other,
            document_id=shared.pk,
            collaborator=self.user,
            role=DocumentAccess.Role.VIEWER,
        )
        DocumentService.get_document(user=self.user, document_id=shared.pk)
        DocumentService.revoke_access(
            user=self.other,
            document_id=shared.pk,
            collaborator=self.user,
        )

        response = self.client.get(reverse("platform_shell:personal_home"))

        self.assertNotIn(shared, response.context["recently_viewed_documents"])
        self.assertNotContains(response, "Revoked document")

    def test_recently_viewed_excludes_inactive_documents(self):
        document = DocumentService.create_document(user=self.user, title="Inactive viewed")
        DocumentService.get_document(user=self.user, document_id=document.pk)
        DocumentService.deactivate_document(user=self.user, document_id=document.pk)

        response = self.client.get(reverse("platform_shell:personal_home"))

        self.assertNotIn(document, response.context["recently_viewed_documents"])
        self.assertNotContains(response, "Inactive viewed")

    def test_personal_home_read_does_not_create_view_audit_events(self):
        document = DocumentService.create_document(user=self.user, title="No synthetic view")
        before = document.audit_log.count()

        response = self.client.get(reverse("platform_shell:personal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(document.audit_log.count(), before)
