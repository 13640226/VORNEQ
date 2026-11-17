"""Chat page wiring for persistent conversations V1 (no model call)."""
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ai_core.tests.test_global_ai_api import DEV, NoNetworkMixin

JS = (Path(settings.BASE_DIR) / "assets" / "js" / "phase-c-chat.js").read_text(encoding="utf-8")
CSS = (Path(settings.BASE_DIR) / "assets" / "css" / "phase-c-chat.css").read_text(encoding="utf-8")


@override_settings(**DEV)
class ConversationPageTests(NoNetworkMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="conv-ui", password="synthetic-only")
        self.client.force_login(self.user)

    def page(self, lang="fa"):
        return self.client.get(reverse("ai_core:chat") + f"?lang={lang}").content.decode()

    def test_flag_off_page_is_unchanged_single_question_mode(self):
        html = self.page()
        self.assertNotIn("data-vq-conversations", html)
        self.assertNotIn("data-vq-conv-panel", html)
        self.assertIn("vq-chat-shell\"", html)

    @override_settings(VORNEQ_AI_CONVERSATIONS_ENABLED=True, VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY="authenticated")
    def test_flag_on_renders_history_notice_and_endpoint(self):
        for lang, title in (("fa", "گفت‌وگوها"), ("de", "Gespräche"), ("en", "Conversations")):
            with self.subTest(lang=lang):
                html = self.page(lang)
                self.assertIn('data-vq-conversations="true"', html)
                self.assertIn(f'data-vq-conv-endpoint="{reverse("ai_core:conversations")}"', html)
                self.assertIn("vq-chat-shell--history", html)
                self.assertIn(title, html)
                self.assertIn("data-vq-conv-notice", html)
                ids = re.findall(r'\sid="([^"]+)"', html)
                self.assertEqual(len(ids), len(set(ids)))
                for target in re.findall(r'(?:for|aria-labelledby)="([^"]+)"', html):
                    self.assertIn(target, ids)

    @override_settings(VORNEQ_AI_CONVERSATIONS_ENABLED=True, VORNEQ_GLOBAL_AI_ENABLED=False,
                       VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY="authenticated")
    def test_conversations_require_global_ai_on_the_page(self):
        self.assertNotIn("data-vq-conversations", self.page())

    @override_settings(VORNEQ_AI_CONVERSATIONS_ENABLED=True, VORNEQ_AI_CONVERSATIONS_ALLOWED_USER_IDS="")
    def test_pilot_allowlist_controls_the_page_independently_of_the_flag(self):
        self.assertNotIn("data-vq-conversations", self.page())
        with override_settings(VORNEQ_AI_CONVERSATIONS_ALLOWED_USER_IDS=str(self.user.pk)):
            self.assertIn('data-vq-conversations="true"', self.page())


class ConversationAssetContractTests(TestCase):
    def test_history_never_stored_in_browser_storage(self):
        self.assertNotRegex(JS, r"localStorage\s*[.\[]")
        self.assertEqual(re.findall(r"sessionStorage\.setItem\(([^,]+),", JS), ["recoveryKey"])
        self.assertNotIn("innerHTML", JS)
        self.assertNotIn("insertAdjacentHTML", JS)

    def test_conversation_is_created_before_any_billable_request(self):
        submit = JS[JS.index('form.addEventListener("submit"'):]
        self.assertLess(submit.index("conv.ensure(question)"), submit.index("saveRecovery("))
        self.assertLess(submit.index("conv.ensure(question)"), submit.index('method: "POST"'))

    def test_ids_from_server_and_url_are_validated(self):
        self.assertIn("uuidPattern.test(String(result.data.conversation.id))", JS)
        self.assertIn("initial && uuidPattern.test(initial)", JS)

    def test_css_logical_properties_and_touch_targets(self):
        block = CSS[CSS.index("/* Persistent conversations V1"):CSS.index("/* Keep citation links readable")]
        self.assertNotRegex(block, r"(margin|padding)-(left|right)\s*:|(?<![-\w])(left|right)\s*:")
        self.assertGreaterEqual(block.count("min-height: 44px"), 6)
