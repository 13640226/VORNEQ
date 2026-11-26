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

        self.assertTemplateUsed(response, "notes/forbidden.html")
        self.assertFalse(UserIdentity.objects.filter(user=unbound).exists())
        self.assertEqual(self.client.get(reverse("notes:create")).status_code, 403)

    def test_inactive_identity_denied(self):
        self.identity.is_active = False
        self.identity.save(update_fields=["is_active"])
        response = self.client.get(reverse("notes:list"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.context["reason"], "inactive")

    def test_missing_binding_translations(self):
        unbound = User.objects.create_user(username="notes-i18n")
        self.client.force_login(unbound)
        expected = {"en": "Notes access restricted", "de": "Zugriff auf Notizen eingeschr\u00e4nkt", "fa": "\u062f\u0633\u062a\u0631\u0633\u06cc \u0628\u0647 \u06cc\u0627\u062f\u062f\u0627\u0634\u062a\u200c\u0647\u0627 \u0645\u062d\u062f\u0648\u062f \u0627\u0633\u062a"}
        for lang, heading in expected.items():
            with self.subTest(lang=lang):
                response = self.client.get(f"/{lang}/notes/")
                self.assertContains(response, heading, status_code=403)
                self.assertEqual(response.context["reason"], "missing")

    def test_other_owner_cannot_read_update_or_delete(self):
        note = NoteService.create_note(user=self.user, title="Private", content="Secret")
        other = User.objects.create_user(username="notes-other-view")
        identity = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name="Other")
        UserIdentity.objects.create(user=other, identity=identity)
        self.client.force_login(other)
        for action in ("detail", "update", "delete"):
            url = reverse(f"notes:{action}", kwargs={"note_id": note.pk})
            response = self.client.get(url) if action == "detail" else self.client.post(url, {"title": "Changed", "content": "Changed"})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.context["reason"], "denied")
            self.assertNotContains(response, "Secret", status_code=403)
        note.refresh_from_db()
        self.assertEqual(note.title, "Private")
        self.assertTrue(note.is_active)

    def test_v8_notes_shell_all_languages(self):
        note = NoteService.create_note(user=self.user, title="V8 private note", content="Private body")
        for lang in ("en", "de", "fa"):
            for suffix in ("", "create/", f"{note.pk}/", f"{note.pk}/update/"):
                with self.subTest(lang=lang, suffix=suffix):
                    response = self.client.get(f"/{lang}/notes/{suffix}")
                    self.assertContains(response, 'id="vq-main"', count=1)
                    self.assertContains(response, "vq-notes-workspace")
            response = self.client.get(f"/{lang}/notes/")
            self.assertContains(response, 'data-note-layout="grid"')
            self.assertContains(response, 'data-note-layout="list"')
        other = User.objects.create_user(username="v8-other")
        self.client.force_login(other)
        response = self.client.get(f"/en/notes/{note.pk}/")
        self.assertContains(response, "vq-notes-workspace", status_code=403)
        self.assertNotContains(response, "Private body", status_code=403)
        self.assertFalse(UserIdentity.objects.filter(user=other).exists())
