from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Identity, UserIdentity
from apps.notes.services import NoteService
from apps.platform_shell.registry import registry


User = get_user_model()


class NoteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="notes-view")
        self.identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Notes View User",
        )
        UserIdentity.objects.create(user=self.user, identity=self.identity)
        self.client.force_login(self.user)

    def test_manifest_is_registered_and_route_resolves(self):
        manifest = registry.get("notes")
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.url_name, "notes:list")
        self.assertEqual(manifest.route_prefix, "notes/")
        self.assertEqual(reverse("notes:list"), manifest and reverse(manifest.url_name))

    def test_note_list_requires_login(self):
        self.client.logout()
        notes_url = reverse("notes:list")
        login_url = reverse("account_login")
        response = self.client.get(notes_url)
        self.assertRedirects(response, f"{login_url}?next={notes_url}")

    def test_create_and_detail_flow(self):
        response = self.client.post(
            reverse("notes:create"),
            {"title": "Flow note", "content": "Hello"},
        )
        note = NoteService.list_notes(self.user).get(title="Flow note")
        self.assertRedirects(response, reverse("notes:detail", kwargs={"note_id": note.pk}))

        detail = self.client.get(reverse("notes:detail", kwargs={"note_id": note.pk}))
        self.assertContains(detail, "Flow note")
        self.assertContains(detail, "Hello")

    def test_delete_requires_post(self):
        note = NoteService.create_note(user=self.user, title="Keep", content="")
        response = self.client.get(reverse("notes:delete", kwargs={"note_id": note.pk}))
        self.assertEqual(response.status_code, 405)

    def test_unbound_user_gets_forbidden_not_implicit_identity(self):
        unbound = User.objects.create_user(username="notes-unbound-view")
        self.client.force_login(unbound)
        response = self.client.get(reverse("notes:list"))
        self.assertEqual(response.status_code, 403)
