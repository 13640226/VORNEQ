"""Notes UI must be fully FA, DE or EN; user-written note content must never change."""
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.html import escape
from django.utils.translation import gettext

from apps.core.models import Identity, UserIdentity
from apps.notes.models import Note
from apps.notes.services import NoteService

User = get_user_model()

LANGUAGES = ("fa", "de", "en")
PERSIAN = re.compile(r"[\u0600-\u06FF]")
USER_TITLE = "Quarterly plan"
USER_BODY = "\u06cc\u0627\u062f\u062f\u0627\u0634\u062a \u0645\u0646"  # Persian user text

# Every English source string the Notes UI renders (templates, manifest, forbidden pages).
LIST_IDS = ("Notes - VORNEQ", "My Notes", "Private notes owned by your bound VORNEQ identity.", "New Note")
DETAIL_IDS = ("Back to Notes", "Note", "Edit", "Delete Note")
CREATE_IDS = ("New Note", "Notes", "Title", "Content", "Save Note", "Back to Notes")
UPDATE_IDS = ("Edit Note", "Notes", "Title", "Content", "Save Note", "Back to Notes")
FORBIDDEN_IDS = {
    "missing": "Your account requires an identity binding. Contact the platform administrator.",
    "inactive": "Your bound identity is inactive. Contact the platform administrator.",
    "denied": "You do not have access to this note.",
}
ALL_IDS = tuple(sorted(set(
    LIST_IDS + DETAIL_IDS + CREATE_IDS + UPDATE_IDS + ("App", "No notes yet.", "Updated %(date)s",
                                                      "Notes access restricted")
    + tuple(FORBIDDEN_IDS.values())
)))


def tr(language, msgid):
    with translation.override(language):
        return gettext(msgid)


# The language switcher shows each language in its own script by design (endonym).
FA_ENDONYM = "\u0641\u0627\u0631\u0633\u06cc"


def ui_text(html):
    """HTML without the user's own note content (never translated) and the FA endonym."""
    return html.replace(USER_BODY, "").replace(USER_TITLE, "").replace(FA_ENDONYM, "")


def make_user(name, *, active=True):
    user = User.objects.create_user(username=name)
    identity = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name=name, is_active=active)
    UserIdentity.objects.create(user=user, identity=identity)
    return user


class NotesLocalizationTests(TestCase):
    def setUp(self):
        self.user = make_user("notes-l10n")
        self.note = NoteService.create_note(user=self.user, title=USER_TITLE, content=USER_BODY)
        self.client.force_login(self.user)

    def url(self, language, name, **kwargs):
        with translation.override(language):
            return reverse(name, kwargs=kwargs)

    def page(self, language, name, expected_status=200, **kwargs):
        response = self.client.get(self.url(language, name, **kwargs))
        self.assertEqual(response.status_code, expected_status, (language, name))
        return response.content.decode("utf-8")

    def assert_pure(self, html, language, ids, label):
        text = ui_text(html)
        for msgid in ids:
            expected = tr(language, msgid)
            # base.html renders the title separator as an em dash.
            variants = (escape(expected), escape(expected.replace(" - ", " \u2014 ")))
            self.assertTrue(any(v in text for v in variants), f"{label}[{language}] missing {msgid!r}")
        # No leakage from the other two languages (identical words such as "App" are exempt).
        for other in LANGUAGES:
            if other == language:
                continue
            for msgid in ALL_IDS:
                foreign, own = tr(other, msgid), tr(language, msgid)
                if foreign == own or "%(" in msgid:
                    continue
                if foreign in own:
                    continue
                self.assertNotIn(escape(foreign), text, f"{label}[{language}] leaks {other}: {msgid!r}")
        if language != "fa":
            self.assertIsNone(PERSIAN.search(text), f"{label}[{language}] contains Persian UI text")

    def assert_direction(self, html, language):
        match = re.search(r'<html[^>]*\bdir="(rtl|ltr)"', html, re.S)
        self.assertIsNotNone(match, language)
        self.assertEqual(match.group(1), "rtl" if language == "fa" else "ltr", language)

    def test_list_page_in_every_language(self):
        for language in LANGUAGES:
            html = self.page(language, "notes:list")
            self.assert_pure(html, language, LIST_IDS, "list")
            self.assert_direction(html, language)
            self.assertIn(USER_TITLE, html)

    def test_empty_list_in_every_language(self):
        self.client.force_login(make_user("notes-l10n-empty"))
        for language in LANGUAGES:
            html = self.page(language, "notes:list")
            self.assert_pure(html, language, LIST_IDS + ("No notes yet.",), "empty-list")

    def test_detail_page_in_every_language(self):
        for language in LANGUAGES:
            html = self.page(language, "notes:detail", note_id=self.note.pk)
            self.assert_pure(html, language, DETAIL_IDS, "detail")
            self.assert_direction(html, language)
            updated = tr(language, "Updated %(date)s") % {"date": timezone.localtime(self.note.updated_at).strftime("%Y-%m-%d")}
            self.assertIn(escape(updated), html)

    def test_create_and_update_forms_in_every_language(self):
        for language in LANGUAGES:
            create = self.page(language, "notes:create")
            self.assert_pure(create, language, CREATE_IDS, "create")
            self.assert_direction(create, language)
            update = self.page(language, "notes:update", note_id=self.note.pk)
            self.assert_pure(update, language, UPDATE_IDS, "update")
            self.assert_direction(update, language)

    def test_validation_errors_follow_the_selected_language(self):
        for language in LANGUAGES:
            response = self.client.post(self.url(language, "notes:create"), {"title": "", "content": "x"})
            self.assertEqual(response.status_code, 200)
            html = response.content.decode("utf-8")
            self.assertIn(escape(tr(language, "This field is required.")), html, language)
            for other in LANGUAGES:
                foreign = tr(other, "This field is required.")
                if foreign != tr(language, "This field is required."):
                    self.assertNotIn(escape(foreign), html, f"{language} leaks {other} error")
        self.assertEqual(Note.objects.count(), 1)

    def test_forbidden_pages_in_every_language(self):
        unbound = User.objects.create_user(username="notes-l10n-unbound")
        inactive = make_user("notes-l10n-inactive", active=False)
        stranger = make_user("notes-l10n-stranger")
        cases = {
            "missing": (unbound, "notes:list", {}),
            "inactive": (inactive, "notes:list", {}),
            "denied": (stranger, "notes:detail", {"note_id": self.note.pk}),
        }
        for reason, (user, name, kwargs) in cases.items():
            self.client.force_login(user)
            for language in LANGUAGES:
                html = self.page(language, name, expected_status=403, **kwargs)
                self.assert_pure(html, language, ("Notes access restricted", FORBIDDEN_IDS[reason]),
                                 f"forbidden-{reason}")
                self.assert_direction(html, language)

    def test_user_content_is_never_translated_or_modified(self):
        before = Note.objects.values_list("title", "content", "updated_at").get(pk=self.note.pk)
        for language in LANGUAGES:
            html = self.page(language, "notes:detail", note_id=self.note.pk)
            self.assertIn(USER_TITLE, html)
            self.assertIn(USER_BODY, html)
            self.page(language, "notes:list")
            self.page(language, "notes:update", note_id=self.note.pk)
        after = Note.objects.values_list("title", "content", "updated_at").get(pk=self.note.pk)
        self.assertEqual(before, after)


class NotesCatalogContractTests(SimpleTestCase):
    def test_every_notes_string_is_translated_in_de_and_fa(self):
        for language in ("de", "fa"):
            for msgid in ALL_IDS + ("Notes",):
                if msgid == "App" and language == "de":
                    continue  # identical in German
                self.assertNotEqual(tr(language, msgid), msgid, f"{language}: {msgid!r} untranslated")
        for msgid in ALL_IDS:
            self.assertIsNone(PERSIAN.search(tr("de", msgid)), msgid)
            self.assertIsNone(PERSIAN.search(tr("en", msgid)), msgid)
        for msgid in ("Notes", "My Notes", "Save Note"):
            self.assertIsNotNone(PERSIAN.search(tr("fa", msgid)), msgid)

    def test_german_uses_real_umlauts_not_transliteration(self):
        for msgid in ALL_IDS:
            text = tr("de", msgid)
            for wrong in ("eingeschraenkt", "benoetigt", "Identitaet", "ueck", "loesch"):
                self.assertNotIn(wrong, text, msgid)

    def test_templates_have_no_hardcoded_visible_text(self):
        folder = Path(__file__).resolve().parents[1] / "templates" / "notes"
        for path in folder.glob("*.html"):
            source = path.read_text(encoding="utf-8")
            self.assertIsNone(PERSIAN.search(source), f"{path.name} hardcodes Persian")
            stripped = re.sub(r"\{%\s*blocktrans(?:late)?\b.*?endblocktrans(?:late)?\s*%\}", "", source, flags=re.S)
            stripped = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", "", stripped, flags=re.S)
            stripped = re.sub(r"<(script|style)\b.*?</\1>", "", stripped, flags=re.S)
            for text in re.findall(r">([^<>]+)<", stripped):
                self.assertIsNone(re.search(r"[A-Za-z]{3,}", text), f"{path.name} hardcodes {text.strip()!r}")
