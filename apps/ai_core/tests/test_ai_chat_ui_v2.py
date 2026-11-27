"""AI chat UI V2: honest environment wording, layout contract, accessibility.

Frontend only. The page never calls a provider; examples never submit.
"""
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.chat_strings import ENVIRONMENT_LABELS, LABELS, UI_LABELS, chat_labels

ASSETS = Path(settings.BASE_DIR) / "assets"
CSS = (ASSETS / "css" / "phase-c-chat.css").read_text(encoding="utf-8")
JS = (ASSETS / "js" / "phase-c-chat.js").read_text(encoding="utf-8")
DEV = dict(VORNEQ_ENV="development", VORNEQ_AI_CORE_ENABLED=True, VORNEQ_AI_PHASE_B_ENABLED=True,
           VORNEQ_AI_PHASE_C_ENABLED=True, VORNEQ_GLOBAL_AI_ENABLED=True)


def render_page(language="en", environment="production", hosts="en.wikipedia.org", recovery=True):
    request = RequestFactory().get("/")
    request.user = mock.Mock(is_authenticated=True)
    return render_to_string("ai_core/chat.html", {
        "chat_labels": chat_labels(language, environment),
        "chat_language": language,
        "chat_endpoint": "/ai/ask/",
        "chat_source_hosts": hosts,
        "chat_staging": environment == "staging",
        "chat_production": environment == "production",
        "chat_recovery_enabled": recovery,
        "chat_recovery_endpoint": "/ai/status/",
    }, request=request)


class EnvironmentWordingTests(SimpleTestCase):
    def test_production_never_shows_preview_or_staging_wording(self):
        for language in ("en", "de", "fa"):
            with self.subTest(language=language):
                labels = chat_labels(language, "production")
                html = render_page(language, "production")
                for forbidden in ("Development preview", "Entwicklungsvorschau", "پیش‌نمایش توسعه",
                                  "Staging", "staging"):
                    self.assertNotIn(forbidden, html)
                    self.assertNotIn(forbidden, labels["entry"] + labels["warning"] + labels["single_turn"])
                self.assertIn(labels["warning"], html)

    def test_staging_and_development_keep_their_own_wording(self):
        self.assertIn("staging", chat_labels("en", "staging")["warning"].lower())
        self.assertIn("Development preview", chat_labels("en", "development")["warning"])
        self.assertIn("Authorized staging trial", render_page("en", "staging"))

    def test_default_environment_comes_from_settings(self):
        with override_settings(VORNEQ_ENV="production"):
            self.assertEqual(chat_labels("de")["entry"], "KI-Chat öffnen")
        with override_settings(VORNEQ_ENV="development"):
            self.assertIn("Entwicklungsvorschau", chat_labels("de")["entry"])

    def test_all_languages_define_the_same_non_empty_keys(self):
        for table in (LABELS, UI_LABELS):
            keys = set(table["en"])
            for language in ("de", "fa"):
                with self.subTest(language=language):
                    self.assertEqual(set(table[language]), keys)
                    self.assertTrue(all(table[language][key] for key in keys))
        for language in ("en", "de", "fa"):
            self.assertEqual(set(ENVIRONMENT_LABELS[language]), {"staging", "production"})
            self.assertEqual(len(UI_LABELS[language]["examples"]), 4)

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(chat_labels("../x", "production")["entry"], "Open AI chat")


class LayoutAndAccessibilityTests(SimpleTestCase):
    def test_examples_are_buttons_and_only_shown_for_global_sources(self):
        html = render_page(hosts="en.wikipedia.org")
        examples = re.findall(r'<button type="button" class="vq-chat__example" data-vq-chat-example>', html)
        self.assertEqual(len(examples), 4)
        self.assertIn("Public encyclopedia articles (Wikipedia)", html)
        local = render_page(hosts="")
        self.assertNotIn("data-vq-chat-example", local)
        self.assertIn("Public VORNEQ sources", local)

    def test_recovery_note_only_when_recovery_is_enabled(self):
        note = UI_LABELS["en"]["recovery_note"]
        self.assertIn(note, render_page(recovery=True))
        self.assertNotIn(note, render_page(recovery=False))

    def test_semantics_ids_and_labels(self):
        for language in ("en", "de", "fa"):
            with self.subTest(language=language):
                html = render_page(language)
                self.assertEqual(html.count("<h1"), 1)
                self.assertEqual(len(re.findall(r'<main\b', html)), 1)
                ids = re.findall(r'\sid="([^"]+)"', html)
                self.assertEqual(len(ids), len(set(ids)))
                for attribute in ("aria-labelledby", "aria-describedby"):
                    for value in re.findall(attribute + r'="([^"]+)"', html):
                        for target in value.split():
                            self.assertIn(target, ids)
                self.assertIn('role="log"', html)
                self.assertIn('<aside class="vq-chat__panel"', html)
                self.assertIn('<details class="vq-chat__info">', html)
                self.assertIn('data-vq-chat-thread', html)
                self.assertRegex(html, r'<button type="submit" class="vq-chat__send"[^>]+disabled>')
                self.assertIn('rows="1" dir="auto"', html)
                self.assertIn(chat_labels(language, "production")["warning"], html)
                self.assertNotIn("style=", html)
                self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)")

    def test_existing_hooks_are_preserved(self):
        html = render_page()
        for hook in ("data-vq-chat", "data-vq-chat-form", "data-vq-chat-input", "data-vq-chat-log",
                     "data-vq-chat-status", "data-vq-chat-send", "data-vq-chat-clear", "data-vq-chat-count",
                     'maxlength="200"', "data-vq-recovery-enabled", "data-vq-source-hosts"):
            self.assertIn(hook, html)


class StaticAssetContractTests(SimpleTestCase):
    def test_examples_fill_input_but_never_submit(self):
        block = JS[JS.index("Example prompts only fill the box"):JS.index("const language =")]
        self.assertIn("input.value =", block)
        for forbidden in ("requestSubmit", "fetch(", "submit()", "dispatchEvent"):
            self.assertNotIn(forbidden, block)

    def test_copy_uses_plain_answer_text_and_no_html(self):
        self.assertIn("navigator.clipboard.writeText(String(answer))", JS)
        self.assertNotIn("innerHTML", JS)
        self.assertNotIn("insertAdjacentHTML", JS)
        self.assertIn('author.textContent', JS)

    def test_css_layout_contract(self):
        self.assertIn("grid-template-columns: minmax(180px, 240px) minmax(0, 1fr)", CSS)
        self.assertIn(".vq-chat__thread", CSS)
        self.assertIn("overflow-y: auto", CSS)
        self.assertIn("scrollbar-width: thin", CSS)
        self.assertIn("text-overflow: ellipsis", CSS)
        self.assertIn("resizeComposer()", JS)
        self.assertNotIn("linear-gradient", CSS)
        self.assertIn("@media (min-width: 1200px)", CSS)
        self.assertIn('window.matchMedia("(max-width: 1199px)")', JS)
        self.assertIn('--vq-led: var(--color-success);', CSS)
        self.assertIn("prefers-reduced-motion: reduce", CSS)
        self.assertIn("forced-colors: active", CSS)
        self.assertNotRegex(CSS, r"(margin|padding)-(left|right)\s*:|(?<![-\w])(left|right)\s*:")
        self.assertNotRegex(CSS, r"\.vq-chat__log:empty\s*\{[^}]*display:\s*none")


class ChatPageIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="chat-ui-v2", email="v2@example.invalid", password="synthetic-only")

    def test_page_renders_v2_without_provider_call(self):
        self.client.force_login(self.user)
        with override_settings(**DEV), \
                mock.patch("apps.ai_core.providers.openai_responses.OpenAIResponsesProvider.generate",
                           side_effect=AssertionError("provider must not be called")):
            response = self.client.get(reverse("ai_core:chat") + "?lang=fa")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('class="vq-chat-shell"', html)
        self.assertIn("هوش مصنوعی VORNEQ", html)
        self.assertIn("data-vq-chat-example", html)
        self.assertIn(f'href="{reverse("search_page")}"', html)

    @override_settings(**DEV)
    def test_workspace_shell_navigation_language_and_preserved_chat(self):
        self.client.force_login(self.user)
        for language in ("fa", "de", "en"):
            with self.subTest(language=language):
                url = reverse("ai_core:chat") + "?lang=" + language
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn('class="vq-shell-body vq-chat-page"', html)
                self.assertIn('id="vq-main"', html)
                self.assertIn('data-vq-drawer', html)
                self.assertIn('data-vq-cmd', html)
                self.assertIn('class="vq-bottomnav"', html)
                self.assertNotIn('class="standalone-nav"', html)
                self.assertIn('dir="rtl"' if language == "fa" else 'dir="ltr"', html)
                self.assertIn(f'href="{reverse("ai_core:chat")}?lang={language}" aria-current="page"', html)
                self.assertIn('data-vq-chat-form', html)
                self.assertIn('csrfmiddlewaretoken', html)
                self.assertIn('no-store', response["Cache-Control"])
                self.assertIn('noindex', response["X-Robots-Tag"])
                for code in ("fa", "de", "en"):
                    self.assertIn(f'value="{reverse("ai_core:chat")}?lang={code}"', html)

    @override_settings(**DEV)
    def test_language_switch_preserves_selected_conversation(self):
        self.client.force_login(self.user)
        cid = "11111111-2222-4333-8444-555555555555"
        response = self.client.get(reverse("ai_core:chat") + "?lang=de&c=" + cid)
        self.assertContains(response, 'data-vq-chat-language-next', count=3)
        self.assertContains(response, f'value="{reverse("ai_core:chat")}?lang=fa&amp;c={cid}"')
