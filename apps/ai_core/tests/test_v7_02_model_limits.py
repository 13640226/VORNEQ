"""V7-02: konfigurierbare Modellgrenzen und professioneller KI-Chat (offline).

Keine Netzwerkzugriffe, keine echten Provider- oder kostenpflichtigen Aufrufe.
Alle Werte sind synthetisch; ``mock-only`` ist kein echtes Modell.
"""
import ast
import json
import os
import time
import uuid
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from apps.ai_core import model_limits as ml
from apps.ai_core.chat_input_budget import LEGACY, global_budget
from apps.ai_core.chat_output_budget import OutputBudget, configured_output_budget
from apps.ai_core.conversations import context
from apps.ai_core.engine.citation import GeneratedAnswerRejected, validate_generated
from apps.ai_core.error_contracts import (BUDGET_REFUSED, CONTEXT_LIMIT_EXCEEDED, EMERGENCY_STOP_ACTIVE,
                                          INPUT_TOO_LARGE, LEDGER_UNAVAILABLE, MODEL_DISABLED,
                                          MODEL_UNAVAILABLE, REASONS, budget_reason, input_too_large,
                                          registry_reason)
from apps.ai_core.gateway import InputError, InputTooLarge, validate
from apps.ai_core.models import AIConversation, AIMessage
from apps.ai_core.views_conversations import _body
from apps.ai_core.views_global import ask_global_view

ROOT = Path(__file__).resolve().parents[3]
LEDGER = dict(VORNEQ_AI_LEDGER_ENABLED=True, VORNEQ_AI_LEDGER_ID="fba6bd94-96bb-4094-818f-84c0935ed211",
              VORNEQ_AI_LEDGER_DB_NAME="test_only", VORNEQ_AI_CHAT_RECOVERY_ENABLED=True,
              VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED=True)
# Fenster 400k, Ausgabe 16k, Eingabe 120k: alle Reserven passen hinein.
CONFIGURED = dict(VORNEQ_ENV="development", VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET="120000",
                  VORNEQ_AI_CHAT_BUDGET_MODEL="mock-only", VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS="400000",
                  VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET="16000")
STAGE2 = dict(VORNEQ_AI_RESPONSE_V3_ENABLED=True, VORNEQ_AI_RESPONSE_V3_STAGE2_ENABLED=True)
TEXTS = {
    "fa": "هوش مصنوعی چگونه کار می‌کند؟",
    "de": "Wie funktionieren Großsprachmodelle über längere Gespräche?",
    "en": "How do large language models handle long conversations?",
    "emoji": "Explain 🚀 and 🌍 briefly 😀",
    "mixed": "VORNEQ چیست und wie works it? ✅",
}


class ModelEnvMixin:
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {"VORNEQ_AI_PHASE_B_MODEL": "mock-only"})
        env.start()
        self.addCleanup(env.stop)


@override_settings(**CONFIGURED)
class CentralPolicyTests(ModelEnvMixin, SimpleTestCase):
    def test_configured_policy_has_all_cor01_fields_and_fits_window(self):
        limits = ml.chat_limits()
        self.assertTrue(limits.extended)
        self.assertEqual((limits.model_id, limits.provider_id, limits.context_window),
                         ("mock-only", "openai-text", 400000))
        self.assertEqual((limits.max_input_tokens, limits.max_output_tokens), (120000, 16000))
        self.assertEqual(limits.reserved_output_tokens, 16000)
        self.assertEqual(limits.token_safety_margin, 20000)
        self.assertEqual(limits.tokenizer_strategy, ml.TOKENIZER_UTF8_UPPER_BOUND)
        self.assertEqual(limits.verification_status, ml.NOT_VERIFIED)
        total = (limits.max_input_tokens + limits.max_output_tokens + limits.system_prompt_tokens
                 + limits.retrieval_context_tokens + limits.token_safety_margin + limits.max_history_tokens)
        self.assertEqual(total, limits.context_window)
        self.assertEqual(limits.max_request_bytes, 6 * 120000 + 512)
        self.assertEqual(limits.conflicts, ())
        for key in ("model_id", "provider_id", "context_window", "max_input_tokens", "max_output_tokens",
                    "max_request_bytes", "max_message_characters", "max_history_tokens",
                    "max_attachment_bytes", "reserved_output_tokens", "system_prompt_tokens",
                    "tool_context_tokens", "retrieval_context_tokens", "token_safety_margin",
                    "tokenizer_strategy", "pricing_reference", "verification_status", "verified_at"):
            self.assertTrue(hasattr(limits, key), key)

    def test_default_is_legacy_200_characters(self):
        with override_settings(VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET=""):
            self.assertEqual(global_budget(), LEGACY)
            self.assertEqual(ml.chat_limits().max_message_characters, 200)

    def test_production_requires_exact_opt_in_ledger_and_recovery(self):
        with override_settings(VORNEQ_ENV="production"):
            self.assertEqual(ml.chat_limits().source, ml.SOURCE_LEGACY)
            self.assertIn("production_opt_in_missing", ml.chat_limits().conflicts)
        for opt_in in ("true", 1, "True", None):
            with self.subTest(opt_in=opt_in), override_settings(
                    VORNEQ_ENV="production", VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT=opt_in, **LEDGER):
                self.assertEqual(global_budget(), LEGACY)
        with override_settings(VORNEQ_ENV="production", VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT=True):
            self.assertEqual(global_budget(), LEGACY)  # kein Ledger -> fail closed
        with override_settings(VORNEQ_ENV="production", VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT=True, **LEDGER):
            self.assertTrue(ml.chat_limits().extended)
        with override_settings(VORNEQ_ENV="production", VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT=True,
                               **dict(LEDGER, VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED=False)):
            self.assertEqual(global_budget(), LEGACY)

    def test_staging_without_ledger_is_legacy(self):
        with override_settings(VORNEQ_ENV="staging"):
            self.assertEqual(global_budget(), LEGACY)
        with override_settings(VORNEQ_ENV="staging", **LEDGER):
            self.assertTrue(ml.chat_limits().extended)

    def test_invalid_environment_and_values_fail_closed(self):
        cases = ({"VORNEQ_ENV": "prod"}, {"VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET": "1e5"},
                 {"VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET": "-1"}, {"VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET": "511"},
                 {"VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS": "abc"},
                 {"VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS": "1000001"},
                 {"VORNEQ_AI_CHAT_BUDGET_MODEL": "other-model"})
        for case in cases:
            with self.subTest(case=case), override_settings(**case):
                self.assertEqual(global_budget(), LEGACY)
                self.assertFalse(ml.chat_limits().extended)

    def test_model_must_match_registered_phase_b_model(self):
        with patch.dict(os.environ, {"VORNEQ_AI_PHASE_B_MODEL": "different"}):
            self.assertIn("budget_model_mismatch", ml.chat_limits().conflicts)

    def test_input_above_window_is_capped_with_conflict_not_guessed(self):
        with override_settings(VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET="999999"):
            limits = ml.chat_limits()
        self.assertTrue(limits.extended)
        self.assertIn("input_budget_above_context", limits.conflicts)
        self.assertEqual(limits.max_input_tokens, 400000 - 16000 - 4000 - 30000 - 20000)
        self.assertLessEqual(limits.max_request_bytes, ml.HARD_MAX_REQUEST_BYTES)

    def test_small_window_falls_back_to_bounded_pilot(self):
        with override_settings(VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS="8192",
                               VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET="1024",
                               VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET="4096"):
            limits = ml.chat_limits()
        self.assertEqual(limits.source, ml.SOURCE_PILOT)
        self.assertIn("context_too_small_for_reservations", limits.conflicts)

    def test_output_is_bounded_by_hard_maximum(self):
        with override_settings(VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET=str(ml.HARD_MAX_OUTPUT_TOKENS + 1),
                               VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS="1000000"):
            limits = ml.chat_limits()
        self.assertLessEqual(limits.max_output_tokens, ml.HARD_MAX_OUTPUT_TOKENS)


class TokenEstimationTests(SimpleTestCase):
    def test_conservative_utf8_upper_bound_per_language(self):
        for name, text in TEXTS.items():
            with self.subTest(language=name):
                tokens = ml.estimate_tokens(text)
                self.assertEqual(tokens, len(text.encode("utf-8")))
                self.assertGreaterEqual(tokens, len(text))  # nie weniger als Zeichen
        self.assertEqual(ml.estimate_tokens("سلام"), 8)            # Persisch: 2 Bytes/Zeichen
        self.assertEqual(ml.estimate_tokens("Größe"), 7)           # Umlaute
        self.assertEqual(ml.estimate_tokens("😀"), 4)               # Emoji
        self.assertEqual(ml.estimate_message_tokens("hi"), 2 + ml.MESSAGE_FRAME_TOKENS)

    def test_unknown_strategy_and_invalid_unicode_fail_closed(self):
        with self.assertRaises(ml.LimitError):
            ml.estimate_tokens("x", strategy="chars")
        with self.assertRaises(ml.LimitError):
            ml.estimate_tokens("\ud800")
        with self.assertRaises(ml.LimitError):
            ml.estimate_tokens(None)


@override_settings(**CONFIGURED)
class InputLengthTests(ModelEnvMixin, SimpleTestCase):
    def test_question_lengths_up_to_50k_and_capacity_boundary(self):
        budget = global_budget()
        self.assertEqual(budget.question_chars, 120000)
        for n in (200, 201, 1000, 10_000, 50_000):
            for name, unit in (("en", "a"), ("fa", "س"), ("de", "ä")):
                question = (unit * n)
                with self.subTest(n=n, language=name):
                    self.assertEqual(validate(question, "en", input_budget=budget)[0], question)
        exact = "a" * 120000
        self.assertEqual(len(validate(exact, "en", input_budget=budget)[0]), 120000)
        with self.assertRaises(InputTooLarge):
            validate(exact + "a", "en", input_budget=budget)
        with self.assertRaises(InputTooLarge):  # 60001 persische Zeichen = 120002 Bytes
            validate("س" * 60001, "fa", input_budget=budget)
        with self.assertRaises(InputTooLarge):  # Emoji zählen 4 Bytes
            validate("😀" * 30001, "en", input_budget=budget)

    def test_legacy_201_is_input_too_large_and_controls_stay_invalid(self):
        with self.assertRaises(InputTooLarge):
            validate("a" * 201, "en")
        self.assertEqual(validate("a" * 200, "en")[0], "a" * 200)
        with self.assertRaises(InputError) as ctx:
            validate("ok\x00", "en", input_budget=global_budget())
        self.assertNotIsInstance(ctx.exception, InputTooLarge)

    def test_50k_validation_is_fast(self):
        budget = global_budget()
        started = time.perf_counter()
        validate("سلام دنیا " * 5000, "fa", input_budget=budget)
        self.assertLess(time.perf_counter() - started, 2.0)


@override_settings(**CONFIGURED)
class HttpContractTests(ModelEnvMixin, SimpleTestCase):
    def request(self, question, **extra):
        request = RequestFactory().post("/api/ai/v1/ask-global/",
                                        data=json.dumps({"question": question, "language": "fa"}),
                                        content_type="application/json", **extra)
        request.user = SimpleNamespace(is_authenticated=True, pk=1)
        request._dont_enforce_csrf_checks = True
        return request

    def call(self, request):
        with patch("apps.ai_core.views_global.global_ai_available", return_value=True), \
                patch("apps.ai_core.views_global.run_global_pipeline",
                      return_value=({"mode": "synthetic"}, 200, {})) as run:
            return ask_global_view(request), run

    def test_long_persian_question_reaches_pipeline_unchanged(self):
        question = "پرسش طولانی " * 4000  # > 40k Zeichen
        response, run = self.call(self.request(question))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(run.call_args.args[1], " ".join(question.split()))

    def test_over_capacity_returns_input_too_large_without_pipeline(self):
        response, run = self.call(self.request("a" * 120001))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content),
                         {"error": "invalid_input", "reason": INPUT_TOO_LARGE, "limit_chars": 120000})
        run.assert_not_called()

    def test_huge_declared_body_rejected_before_reading(self):
        request = self.request("x")
        request.META["CONTENT_LENGTH"] = str(50 * 1024 * 1024)
        with patch.object(type(request), "body", new_callable=lambda: property(
                lambda _self: (_ for _ in ()).throw(AssertionError("body read")))):
            response, run = self.call(request)
        self.assertEqual(response.status_code, 413)
        body = json.loads(response.content)
        self.assertEqual((body["error"], body["reason"]), ("request_too_large", INPUT_TOO_LARGE))
        self.assertEqual(body["limit_bytes"], 6 * 120000 + 512)
        run.assert_not_called()

    def test_legacy_http_contract_unchanged_for_valid_and_201(self):
        with override_settings(VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET=""):
            response, _run = self.call(self.request("a" * 201))
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.content)["error"], "invalid_input")
            response, _run = self.call(self.request("a" * 3000))
            self.assertEqual(response.status_code, 413)
            self.assertEqual(json.loads(response.content)["error"], "request_too_large")

    def test_conversation_body_uses_same_budget(self):
        question = "a" * 50_000
        self.assertEqual(_body(self.request(question), {"question", "language"},
                               max_body=global_budget().body_bytes)["question"], question)
        with self.assertRaisesRegex(ValueError, "request_too_large"):
            _body(self.request("a" * 800_000), {"question", "language"}, max_body=global_budget().body_bytes)


@override_settings(**dict(CONFIGURED, **STAGE2))
class OutputBudgetTests(ModelEnvMixin, SimpleTestCase):
    def test_large_output_only_with_complete_policy(self):
        budget = configured_output_budget()
        self.assertEqual(budget.output_tokens, 16000)
        self.assertEqual(budget.answer_chars, 8 * 16000)
        self.assertEqual(budget.section_chars, 8 * 16000 // 6)
        with override_settings(VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET=""):
            self.assertIsNone(configured_output_budget())  # ohne Policy bleibt 8192 der Deckel
        with override_settings(VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET="", VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET="8192"):
            self.assertEqual(configured_output_budget().output_tokens, 8192)
        with override_settings(VORNEQ_ENV="production"):
            self.assertIsNone(configured_output_budget())  # Production-Ausgabe unverändert

    def test_context_check_includes_safety_margin_before_reservation(self):
        from apps.ai_core.providers.exceptions import ProviderContextLimited
        from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
        from apps.ai_ledger.service import INPUT_OVERHEAD_TOKENS
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-only"}):
            provider = OpenAIResponsesProvider(model="mock-only", timeout_s=5, max_output_tokens=16000,
                                               response_v3_enabled=True, response_stage2_enabled=True)
        limit = 400000 - 16000 - 20000 - INPUT_OVERHEAD_TOKENS
        provider.check_context_budget(limit)  # exakt an der Grenze erlaubt
        with self.assertRaises(ProviderContextLimited):
            provider.check_context_budget(limit + 1)

    def test_section_bound_never_below_previous_value(self):
        self.assertEqual(OutputBudget("m", 1536, 8192).section_chars, 2048)
        self.assertEqual(OutputBudget("m", 1536, 8192).answer_chars, 12288)

    def test_no_fixed_2400_bound_in_citation_validator(self):
        with self.assertRaises(GeneratedAnswerRejected):
            validate_generated({}, sources=[], language="en", max_answer_chars=ml.MAX_VALIDATED_ANSWER_CHARS + 1)

    def test_provider_accepts_larger_cap_constructor_only(self):
        from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-only"}):
            provider = OpenAIResponsesProvider(model="mock-only", timeout_s=5, max_output_tokens=16000,
                                               response_v3_enabled=True, response_stage2_enabled=True)
        self.assertEqual(provider.max_output_tokens, 16000)
        instructions = provider.instructions_for("What is quantum computing?", "en", mode="sectioned")
        self.assertIn(f"at most {8 * 16000 // 6} characters per answer section", instructions)


@override_settings(**CONFIGURED)
class ContextPlanTests(ModelEnvMixin, SimpleTestCase):
    def test_plan_counts_every_component(self):
        limits = ml.chat_limits()
        plan = ml.plan_context(limits, system_prompt="s" * 100, user_prompt="سلام",
                               history=({"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}),
                               sources_text="src", tool_context="t", attachments_bytes=5)
        self.assertEqual(plan.system_prompt, 100)
        self.assertEqual(plan.user_prompt, 8 + ml.MESSAGE_FRAME_TOKENS)
        self.assertEqual(plan.history, 2 * (1 + ml.MESSAGE_FRAME_TOKENS))
        self.assertEqual((plan.retrieved_sources, plan.tool_context, plan.attachments), (3, 1, 5))
        self.assertEqual(plan.reserved_output, 16000)
        self.assertTrue(plan.fits)

    def test_overflow_raises_context_limit_exceeded(self):
        limits = ml.chat_limits()
        with self.assertRaises(ml.ContextLimitExceeded):
            ml.plan_context(limits, user_prompt="a" * 400000)
        plan = ml.plan_context(limits, user_prompt="a" * 400000, raise_on_overflow=False)
        self.assertFalse(plan.fits)
        with override_settings(VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET=""), self.assertRaises(ml.ContextLimitExceeded):
            ml.plan_context(ml.chat_limits(), user_prompt="x")

    def test_select_history_whole_pairs_newest_kept_order_preserved(self):
        limits = ml.chat_limits()
        small = ml.ModelLimits(**{**limits.__dict__, "max_history_tokens": 2 * (10 + 8) * 2})
        pairs = [("q3" + "x" * 8, "a3" + "x" * 8), ("q2" + "x" * 8, "a2" + "x" * 8), ("q1" + "x" * 8, "a1" + "x" * 8)]
        turns = ml.select_history(pairs, small)
        self.assertEqual([t["content"][:2] for t in turns], ["q2", "a2", "q3", "a3"])
        self.assertEqual([t["role"] for t in turns], ["user", "assistant"] * 2)
        self.assertEqual(ml.select_history(pairs, ml.ModelLimits(**{**limits.__dict__, "max_history_tokens": 0})), ())


@override_settings(**CONFIGURED)
class ConversationContextTests(ModelEnvMixin, TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.owner = User.objects.create_user(username="v702-owner", email="o@example.invalid", password="x-1!Aa-long")
        self.other = User.objects.create_user(username="v702-other", email="p@example.invalid", password="x-1!Aa-long")
        self.conversation = AIConversation.objects.create(owner=self.owner)
        seq = 0
        for i in range(30):
            for role, text in ((AIMessage.ROLE_USER, f"Frage {i} " + "ü" * 1500),
                               (AIMessage.ROLE_ASSISTANT, f"Antwort {i} " + "پاسخ " * 600)):
                seq += 1
                AIMessage.objects.create(conversation=self.conversation, sequence=seq, role=role,
                                         content=text, status=AIMessage.STATUS_COMPLETED)

    def test_budgeted_history_includes_long_messages_in_order(self):
        turns = context.prior_turns(self.conversation)
        self.assertGreater(len(turns), 12)  # mehr als die feste Turn-Zahl (6 Paare)
        self.assertEqual(turns[-2]["content"][:9], "Frage 29 ")
        self.assertEqual([t["role"] for t in turns[:2]], ["user", "assistant"])
        used = sum(ml.estimate_message_tokens(t["content"]) for t in turns)
        self.assertLessEqual(used, ml.chat_limits().max_history_tokens)
        self.assertEqual(AIMessage.objects.filter(conversation=self.conversation).count(), 60)  # Speicher unverändert

    def test_legacy_history_unchanged(self):
        with override_settings(VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET=""):
            self.assertEqual(context.prior_turns(self.conversation), ())  # >1000 Zeichen: wie bisher übersprungen

    def test_history_is_per_conversation_owner(self):
        foreign = AIConversation.objects.create(owner=self.other)
        self.assertEqual(context.prior_turns(foreign), ())
        from apps.ai_core.conversations import repository
        from apps.ai_core.conversations.repository import ConversationNotFound
        with self.assertRaises(ConversationNotFound):
            repository.get_conversation(self.other, self.conversation.id)


class ErrorContractTests(SimpleTestCase):
    def test_reason_mapping_for_ledger_states(self):
        from apps.ai_core.engine.budget import BudgetExceeded
        from apps.ai_ledger.service import BudgetExhausted, EmergencyStop, LedgerUnavailable
        self.assertEqual(budget_reason(EmergencyStop("secret detail")), EMERGENCY_STOP_ACTIVE)
        self.assertEqual(budget_reason(LedgerUnavailable("dsn=postgres://u:p@h")), LEDGER_UNAVAILABLE)
        self.assertEqual(budget_reason(BudgetExhausted("x")), BUDGET_REFUSED)
        self.assertEqual(budget_reason(BudgetExceeded("x")), BUDGET_REFUSED)

    def test_registry_reason_mapping(self):
        from apps.ai_core.provider_registry import ModelDisabled, ModelUnavailable
        self.assertEqual(registry_reason(ModelDisabled("x")), MODEL_DISABLED)
        self.assertEqual(registry_reason(ModelUnavailable("x")), MODEL_UNAVAILABLE)
        self.assertIn(registry_reason(object()), REASONS)

    def test_payload_contains_only_fixed_fields(self):
        self.assertEqual(input_too_large("invalid_input", limit_chars=5),
                         {"error": "invalid_input", "reason": INPUT_TOO_LARGE, "limit_chars": 5})
        self.assertEqual(input_too_large("x", limit_chars=True, limit_bytes=-1), {"error": "x", "reason": INPUT_TOO_LARGE})
        self.assertIn(CONTEXT_LIMIT_EXCEEDED, REASONS)
        self.assertEqual(len(REASONS), 9)


class ReportAndGuardTests(ModelEnvMixin, SimpleTestCase):
    @override_settings(**CONFIGURED)
    def test_report_lists_limits_without_secrets_or_network(self):
        out = StringIO()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-synthetic-never-print"}), \
                patch("socket.socket", side_effect=AssertionError("network")):
            call_command("ai_gateway_report", "--json", stdout=out)
        text = out.getvalue()
        self.assertNotIn("sk-synthetic-never-print", text)
        section = json.loads(text)["chat_limits"]
        self.assertEqual(section["source"], ml.SOURCE_CONFIGURED)
        for key in ("context_window", "max_input_tokens", "effective_output_tokens", "max_history_tokens",
                    "tokenizer_strategy", "conflicts", "verification_status", "disabled_reasons", "ledger_status"):
            self.assertIn(key, section)
        out = StringIO()
        call_command("ai_gateway_report", stdout=out)
        self.assertIn("chat limits: source=OPERATOR_CONFIGURED", out.getvalue())

    def test_new_modules_have_no_direct_sdk_or_network_imports(self):
        for name in ("model_limits.py", "error_contracts.py"):
            tree = ast.parse((ROOT / "apps" / "ai_core" / name).read_text(encoding="utf-8"))
            imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                        if isinstance(node, ast.Import) for alias in node.names}
            imported |= {(node.module or "").split(".")[0] for node in ast.walk(tree)
                         if isinstance(node, ast.ImportFrom)}
            self.assertFalse(imported & {"openai", "httpx", "requests", "urllib", "socket"}, name)


@override_settings(**CONFIGURED, VORNEQ_AI_CORE_ENABLED=True, VORNEQ_AI_PHASE_B_ENABLED=True,
                   VORNEQ_AI_PHASE_C_ENABLED=True, VORNEQ_GLOBAL_AI_ENABLED=True)
class FrontendContractTests(ModelEnvMixin, TestCase):
    def test_chat_page_exposes_policy_limits_and_keeps_typed_text(self):
        from django.urls import reverse
        User = get_user_model()
        user = User.objects.create_user(username=f"v702-{uuid.uuid4().hex[:6]}", email="f@example.invalid",
                                        password="x-1!Aa-long", is_staff=True, is_superuser=True)
        self.client.force_login(user)
        html = self.client.get(reverse("ai_core:chat") + "?lang=fa").content.decode()
        self.assertIn('maxlength="120000"', html)
        self.assertIn('data-vq-question-limit="120000"', html)
        self.assertIn("data-vq-input-too-large=", html)
        js = (ROOT / "assets" / "js" / "phase-c-chat.js").read_text(encoding="utf-8")
        self.assertNotIn("rawLimit <= 8192", js)
        self.assertNotIn("rawSectionLimit <= 1400", js)
        self.assertIn('if (completed && answerBubble) input.value = "";', js)
        self.assertIn('data.reason === "INPUT_TOO_LARGE"', js)
