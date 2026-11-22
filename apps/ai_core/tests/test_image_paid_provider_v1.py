"""Paid OpenAI image provider readiness: fake SDK only, no network, no billing.

The real ``openai`` package is replaced in sys.modules by a recording fake, so
these tests run identically with or without the SDK installed.
"""
import base64
import hashlib
import io
import sys
import types
from unittest.mock import patch

from PIL import Image
from django.test import SimpleTestCase, override_settings

from apps.ai_core.image_generation import policy
from apps.ai_core.image_generation.providers import (
    ImageProviderError, OpenAIImageProvider, classify_provider_exception,
)

MODEL = "gpt-image-2.6-flare"
KEY = "synthetic-offline-test-key-not-a-secret-0001"
SAFETY = "vq_" + "a" * 64
SECRET_TEXT = "PROMPT-SECRET sk-live-should-never-leak"


def png_b64():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (10, 20, 30)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def sdk_error(name, status=None, code=None):
    cls = type(name, (Exception,), {})
    exc = cls(SECRET_TEXT)
    if status is not None:
        exc.status_code = status
    if code is not None:
        exc.code = code
    return exc


class FakeSDK:
    def __init__(self, *, flagged=False, moderation_error=None, generate_error=None,
                 response=None, ctor_error=None):
        self.calls, self.ctor_kwargs = [], None
        self.flagged, self.moderation_error = flagged, moderation_error
        self.generate_error, self.ctor_error = generate_error, ctor_error
        self.response = response if response is not None else types.SimpleNamespace(
            data=[types.SimpleNamespace(b64_json=png_b64())],
            usage=types.SimpleNamespace(input_tokens=12, output_tokens=310))

    def module(self):
        sdk = self
        mod = types.ModuleType("openai")

        class OpenAI:
            def __init__(self, **kwargs):
                if sdk.ctor_error:
                    raise sdk.ctor_error
                sdk.ctor_kwargs = kwargs
                self.moderations = types.SimpleNamespace(create=self._moderate)
                self.images = types.SimpleNamespace(generate=self._generate)

            def _moderate(self, **kwargs):
                sdk.calls.append(("moderations", kwargs))
                if sdk.moderation_error:
                    raise sdk.moderation_error
                return types.SimpleNamespace(results=[types.SimpleNamespace(flagged=sdk.flagged)])

            def _generate(self, **kwargs):
                sdk.calls.append(("images", kwargs))
                if sdk.generate_error:
                    raise sdk.generate_error
                return sdk.response

        mod.OpenAI = OpenAI
        return mod

    def image_calls(self):
        return [kw for name, kw in self.calls if name == "images"]


PAID = dict(VORNEQ_AI_IMAGE_MODEL=MODEL, VORNEQ_AI_IMAGE_COMPLEXITY="low",
            VORNEQ_AI_IMAGE_SAFETY_ID_KEY=KEY)


@override_settings(**PAID)
class PaidProviderTests(SimpleTestCase):
    def run_provider(self, sdk, *, safety=SAFETY, gate=True):
        with patch.dict(sys.modules, {"openai": sdk.module()}), \
                patch.dict("os.environ", {"VORNEQ_OPENAI_IMAGE_API_KEY": "synthetic-never-live"}), \
                patch.object(policy, "paid_provider_enabled", return_value=gate):
            return OpenAIImageProvider().generate(prompt="A small green leaf", model=MODEL,
                                                  size="1024x1024", safety_identifier=safety)

    def assert_error(self, sdk, code, sent, **kw):
        with self.assertRaises(ImageProviderError) as ctx:
            self.run_provider(sdk, **kw)
        self.assertEqual((ctx.exception.code, ctx.exception.request_sent), (code, sent))
        self.assertNotIn("PROMPT-SECRET", str(ctx.exception))
        self.assertNotIn("sk-live", str(ctx.exception))
        return ctx.exception

    def test_success_sends_exact_safe_parameters_once(self):
        sdk = FakeSDK()
        result = self.run_provider(sdk)
        self.assertEqual((result.input_tokens, result.output_tokens, result.is_mock),
                         (12, 310, False))
        self.assertEqual(sdk.ctor_kwargs["max_retries"], 0)
        self.assertEqual(sdk.ctor_kwargs["api_key"], "synthetic-never-live")
        self.assertEqual(sdk.image_calls(), [dict(
            model=MODEL, prompt="A small green leaf", n=1, size="1024x1024", quality="low",
            output_format="png", moderation="auto", complexity="low",
            safety_identifier=SAFETY)])

    def test_real_provider_adapter_accepts_separately_authorized_paid_worker(self):
        sdk = FakeSDK()
        with (patch.dict(sys.modules, {"openai": sdk.module()}),
              patch.dict("os.environ", {"VORNEQ_OPENAI_IMAGE_API_KEY": "synthetic-never-live"}),
              patch.object(policy, "paid_provider_enabled", return_value=False),
              patch.object(policy, "paid_worker_enabled", return_value=True)):
            result = OpenAIImageProvider().generate(
                prompt="Offline worker regression", model=MODEL, size="1024x1024",
                safety_identifier=SAFETY)
        self.assertFalse(result.is_mock)
        self.assertEqual(len(sdk.image_calls()), 1)

    def test_both_paid_gates_closed_never_constructs_sdk(self):
        sdk = FakeSDK()
        with patch.object(policy, "paid_worker_enabled", return_value=False):
            self.assert_error(sdk, "paid_disabled", False, gate=False)
        self.assertIsNone(sdk.ctor_kwargs)
        self.assertEqual(sdk.image_calls(), [])

    def test_dedicated_image_key_never_uses_chat_key(self):
        sdk = FakeSDK()
        with (patch.dict(sys.modules, {"openai": sdk.module()}),
              patch.dict("os.environ", {
                  "OPENAI_API_KEY": "synthetic-chat-project-key",
                  "VORNEQ_OPENAI_IMAGE_API_KEY": "synthetic-image-project-key",
              }),
              patch.object(policy, "paid_provider_enabled", return_value=True)):
            OpenAIImageProvider().generate(
                prompt="A small green leaf", model=MODEL, size="1024x1024",
                safety_identifier=SAFETY)
        self.assertEqual(sdk.ctor_kwargs["api_key"], "synthetic-image-project-key")
        self.assertNotEqual(sdk.ctor_kwargs["api_key"], "synthetic-chat-project-key")
        self.assertEqual(len(sdk.image_calls()), 1)

    def test_missing_image_key_never_falls_back_to_chat_key(self):
        sdk = FakeSDK()
        with (patch.dict(sys.modules, {"openai": sdk.module()}),
              patch.dict("os.environ", {
                  "OPENAI_API_KEY": "synthetic-chat-project-key",
                  "VORNEQ_OPENAI_IMAGE_API_KEY": "",
              }),
              patch.object(policy, "paid_provider_enabled", return_value=True)):
            with self.assertRaises(ImageProviderError) as caught:
                OpenAIImageProvider().generate(
                    prompt="A small green leaf", model=MODEL, size="1024x1024",
                    safety_identifier=SAFETY)
        self.assertEqual((caught.exception.code, caught.exception.request_sent),
                         ("image_api_key_missing", False))
        self.assertIsNone(sdk.ctor_kwargs)

    def test_moderation_block_is_not_sent(self):
        sdk = FakeSDK(flagged=True)
        self.assert_error(sdk, "prompt_moderated", False)
        self.assertEqual(sdk.image_calls(), [])

    def test_moderation_endpoint_failure_is_not_sent(self):
        sdk = FakeSDK(moderation_error=sdk_error("APIConnectionError"))
        self.assert_error(sdk, "moderation_unavailable", False)
        self.assertEqual(sdk.image_calls(), [])

    def test_provider_http_and_transport_errors_stay_possibly_billed(self):
        cases = {
            "provider_moderation_blocked": sdk_error("BadRequestError", 400, "moderation_blocked"),
            "provider_bad_request": sdk_error("BadRequestError", 400),
            "provider_auth": sdk_error("AuthenticationError", 401),
            "provider_permission": sdk_error("PermissionDeniedError", 403),
            "provider_rate_limited": sdk_error("RateLimitError", 429),
            "provider_server_error": sdk_error("InternalServerError", 500),
            "provider_timeout": sdk_error("APITimeoutError"),
            "provider_connection": sdk_error("APIConnectionError"),
            "provider_outcome_uncertain": RuntimeError(SECRET_TEXT),
        }
        for code, error in cases.items():
            with self.subTest(code):
                sdk = FakeSDK(generate_error=error)
                self.assert_error(sdk, code, True)
                self.assertEqual(len(sdk.image_calls()), 1)  # exactly one attempt, no retry

    def test_empty_invalid_and_missing_usage_responses(self):
        empty = FakeSDK(response=types.SimpleNamespace(data=[], usage=None))
        self.assert_error(empty, "provider_empty_response", True)
        bad = FakeSDK(response=types.SimpleNamespace(
            data=[types.SimpleNamespace(b64_json="!!notbase64!!")], usage=None))
        self.assert_error(bad, "provider_invalid_image", True)
        not_png = FakeSDK(response=types.SimpleNamespace(
            data=[types.SimpleNamespace(b64_json=base64.b64encode(b"<html>").decode())],
            usage=None))
        self.assert_error(not_png, "provider_invalid_image", True)
        no_usage = FakeSDK(response=types.SimpleNamespace(
            data=[types.SimpleNamespace(b64_json=png_b64())], usage=None))
        result = self.run_provider(no_usage)
        self.assertEqual((result.input_tokens, result.output_tokens), (None, None))

    def test_pre_send_refusals_never_construct_the_sdk(self):
        for kw, code in (({"gate": False}, "paid_disabled"),
                         ({"safety": None}, "safety_identifier_unavailable"),
                         ({"safety": "user-42"}, "safety_identifier_unavailable")):
            with self.subTest(code=code, kw=kw):
                sdk = FakeSDK()
                self.assert_error(sdk, code, False, **kw)
                self.assertIsNone(sdk.ctor_kwargs)
        with override_settings(VORNEQ_AI_IMAGE_COMPLEXITY="extreme"):
            sdk = FakeSDK()
            self.assert_error(sdk, "invalid_configuration", False)
            self.assertIsNone(sdk.ctor_kwargs)
        sdk = FakeSDK(ctor_error=RuntimeError(SECRET_TEXT))
        self.assert_error(sdk, "sdk_unavailable", False)

    def test_classifier_never_reads_exception_text(self):
        self.assertEqual(classify_provider_exception(ValueError("429 rate limit")),
                         "provider_outcome_uncertain")


class SafetyIdentifierTests(SimpleTestCase):
    def test_hmac_is_stable_keyed_and_not_a_plain_hash(self):
        with override_settings(VORNEQ_AI_IMAGE_SAFETY_ID_KEY=KEY):
            first, again = policy.safety_identifier(42), policy.safety_identifier(42)
            other = policy.safety_identifier(43)
        with override_settings(VORNEQ_AI_IMAGE_SAFETY_ID_KEY=KEY + "-rotated"):
            rotated = policy.safety_identifier(42)
        self.assertEqual(first, again)
        self.assertRegex(first, r"\Avq_[0-9a-f]{64}\Z")
        self.assertNotEqual(first, other)
        self.assertNotEqual(first, rotated)
        for plain in (hashlib.sha256(b"42").hexdigest(), hashlib.sha256(b"user:42").hexdigest()):
            self.assertNotEqual(first[3:], plain)

    def test_missing_or_short_key_or_bad_user_disables(self):
        for key in ("", "short", " " * 40):
            with self.subTest(key=key), override_settings(VORNEQ_AI_IMAGE_SAFETY_ID_KEY=key):
                self.assertFalse(policy.safety_key_ready())
                self.assertIsNone(policy.safety_identifier(42))
        with override_settings(VORNEQ_AI_IMAGE_SAFETY_ID_KEY=KEY):
            for bad in (0, -1, "42", None, True):
                self.assertIsNone(policy.safety_identifier(bad))


class PaidGateConfigurationTests(SimpleTestCase):
    """paid_provider_enabled stays False unless every new money control is set."""

    BASE = dict(VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD=50_000, VORNEQ_AI_IMAGE_SAFETY_ID_KEY=KEY,
                VORNEQ_AI_IMAGE_COMPLEXITY="low", VORNEQ_ENV="staging",
                VORNEQ_AI_IMAGE_PROVIDER="openai", VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=True,
                VORNEQ_AI_IMAGE_MODEL=MODEL, VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND=2_000,
                VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=100_000)

    def enabled_with(self, **over):
        values = dict(self.BASE, **over)
        with override_settings(**values), \
                patch.object(policy, "enabled", return_value=True), \
                patch.object(policy, "image_ledger_config", return_value=object()), \
                patch("apps.ai_core.image_generation.storage.durable_storage_ready",
                      return_value=True), \
                patch.dict("os.environ", {"VORNEQ_OPENAI_IMAGE_API_KEY": "synthetic-never-live"}):
            return policy.paid_provider_enabled()

    def test_all_controls_set_opens_only_in_process(self):
        self.assertTrue(self.enabled_with())

    def test_each_missing_control_closes(self):
        for over in ({"VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD": 0},
                     {"VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD": policy.MAX_REQUEST_CEILING_MICRO + 1},
                     {"VORNEQ_AI_IMAGE_SAFETY_ID_KEY": ""},
                     {"VORNEQ_AI_IMAGE_COMPLEXITY": "ultra"},
                     {"VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND": 0},
                     {"VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False}):
            with self.subTest(over):
                self.assertFalse(self.enabled_with(**over))

    def test_chat_key_only_keeps_paid_image_gate_closed(self):
        with (override_settings(**self.BASE),
              patch.object(policy, "enabled", return_value=True),
              patch.object(policy, "image_ledger_config", return_value=object()),
              patch("apps.ai_core.image_generation.storage.durable_storage_ready",
                    return_value=True),
              patch.dict("os.environ", {
                  "OPENAI_API_KEY": "synthetic-chat-project-key",
                  "VORNEQ_OPENAI_IMAGE_API_KEY": "",
              })):
            self.assertFalse(policy.paid_provider_enabled())

    def test_whitespace_image_key_fails_closed(self):
        with (override_settings(**self.BASE),
              patch.object(policy, "enabled", return_value=True),
              patch.object(policy, "image_ledger_config", return_value=object()),
              patch("apps.ai_core.image_generation.storage.durable_storage_ready",
                    return_value=True),
              patch.dict("os.environ", {
                  "VORNEQ_OPENAI_IMAGE_API_KEY": "   ",
              })):
            self.assertFalse(policy.paid_provider_enabled())

    def test_official_price_reference(self):
        self.assertEqual(policy.OFFICIAL_PRICES_MICRO_PER_MTOK[MODEL], (5_000_000, 30_000_000))
