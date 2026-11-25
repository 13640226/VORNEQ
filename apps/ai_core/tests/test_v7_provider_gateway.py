"""V7-01 — Provider/Model Registry und Gateway-Auflösung (Pflichttests).

Offline: keine Netzwerkaufrufe, keine Schlüssel, keine bezahlten Requests.
Das OpenAI-SDK wird in den Laufzeittests durch einen Stolperdraht ersetzt.
"""
import ast
import io
import json
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.ai_core import provider_registry as reg
from apps.ai_core.provider_registry import (
    CATALOG, LEGACY_POLICY, Capability, ModelSpec, ProviderSpec, ProviderType, Registry,
)
from apps.ai_core.provider_resolution import Resolution, resolve
from apps.ai_core.tests.ledger_fakes import fake_reservation, start_fake_ledger
from apps.ai_ledger.call_authorization import (
    UnauthorizedPaidCall, authorized_paid_call, require_authorized_paid_call,
)

ROOT = Path(settings.BASE_DIR)
DEV = dict(VORNEQ_ENV="development", VORNEQ_AI_EMERGENCY_STOP=False)
STAGING = dict(VORNEQ_ENV="staging", VORNEQ_AI_EMERGENCY_STOP=False)
USER = SimpleNamespace(is_authenticated=True, is_active=True, pk=7)


def provider(pid="p", caps=(Capability.TEXT_GENERATION,), paid=True, **kw):
    return ProviderSpec(pid, set(caps), paid, **kw)


class RegistryValidationTests(SimpleTestCase):
    def test_catalog_is_valid_and_contains_only_existing_providers(self):
        self.assertEqual({p.provider_id for p in CATALOG.providers()},
                         {"openai-text", "openai-image", "mock-image", "mock-voice"})
        self.assertTrue(all(not p.paid for p in CATALOG.providers() if p.provider_type is ProviderType.MOCK))

    def test_all_cor02_capabilities_exist_without_implying_implementation(self):
        names = {"TEXT_GENERATION", "STRUCTURED_OUTPUT", "STREAMING", "TOOL_CALLING", "IMAGE_GENERATION",
                 "IMAGE_EDITING", "EMBEDDING", "SPEECH_TO_TEXT", "TEXT_TO_SPEECH", "REALTIME_VOICE",
                 "VIDEO_GENERATION", "MUSIC_GENERATION", "THREE_D_GENERATION"}
        self.assertTrue(names <= set(Capability.__members__))
        for capability in (Capability.EMBEDDING, Capability.VIDEO_GENERATION):
            self.assertEqual(CATALOG.providers_for(capability), ())
        # V7-03: Streaming ist für openai-text implementiert (ADR-0009).
        self.assertEqual([p.provider_id for p in CATALOG.providers_for(Capability.STREAMING)], ["openai-text"])
        self.assertIs(Capability.TEXT, Capability.TEXT_GENERATION)  # Alias aus #743

    def test_duplicate_provider_and_duplicate_model(self):
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([provider(), provider()])
        p = provider(paid=False, provider_type=ProviderType.MOCK)
        m = ModelSpec("m", "p", {Capability.TEXT_GENERATION}, enabled=True)
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([p], [m, m])

    def test_unknown_provider_for_model_and_invalid_capability(self):
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([provider()], [ModelSpec("m", "other", {Capability.TEXT_GENERATION})])
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([provider(caps=("text_generation",))])
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([provider()], [ModelSpec("m", "p", {Capability.IMAGE_GENERATION})])

    def test_new_paid_model_requires_verified_pricing(self):
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([provider()], [ModelSpec("m", "p", {Capability.TEXT_GENERATION}, enabled=True,
                                              pricing_reference="https://example.invalid/price")])
        ok = Registry([provider()], [ModelSpec("m", "p", {Capability.TEXT_GENERATION}, enabled=True,
                                               pricing_reference="https://example.invalid/price",
                                               pricing_verified_at="2026-11-25")])
        self.assertTrue(ok.model("p", "m").enabled)
        # Ein deaktivierter neuer Eintrag ohne Preis ist erlaubt (nicht nutzbar).
        Registry([provider()], [ModelSpec("m", "p", {Capability.TEXT_GENERATION})])

    def test_verified_claims_need_date_and_documentation(self):
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([provider(dpa_status=reg.VERIFIED)])
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([provider(dpa_status="COMPLIANT")])
        Registry([provider(dpa_status=reg.VERIFIED, verified_at="2026-11-25",
                           documentation_url="https://example.invalid/dpa")])

    def test_mock_provider_can_never_be_paid(self):
        with self.assertRaises(reg.InvalidConfiguration):
            Registry([provider(paid=True, provider_type=ProviderType.MOCK)])

    def test_unverified_values_are_marked_not_verified(self):
        for spec in CATALOG.providers():
            if spec.provider_type is ProviderType.EXTERNAL_API:
                self.assertEqual((spec.dpa_status, spec.data_retention_status, spec.compliance_review_status,
                                  spec.data_processing_region), ("NOT_VERIFIED",) * 4)
                self.assertIsNone(spec.verified_at)
        for model in CATALOG.models():
            self.assertIsNone(model.pricing_reference)
            self.assertIsNone(model.context_window)

    def test_existing_models_are_legacy_governed_and_policy_list_unchanged(self):
        from apps.ai_core.image_generation.policy import MODELS
        self.assertEqual(MODELS, frozenset({"gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst",
                                            "gpt-image-2.6-flare", "gpt-image-2.6-sunburst"}))
        self.assertEqual({m.model_id for m in CATALOG.models("openai-image")}, MODELS)
        self.assertTrue(all(m.availability_status == LEGACY_POLICY for m in CATALOG.models()))

    def test_unknown_and_disabled_models_and_providers(self):
        with self.assertRaises(reg.ModelUnavailable):
            CATALOG.model("openai-text", "unknown")
        r = Registry([provider(), provider("q", enabled=False)],
                     [ModelSpec("off", "p", {Capability.TEXT_GENERATION})])
        with self.assertRaises(reg.ModelDisabled):
            r.model("p", "off")
        with self.assertRaises(reg.ProviderDisabled):
            r.provider("q", Capability.TEXT_GENERATION)
        with self.assertRaises(reg.ProviderUnavailable):
            r.provider("nope", Capability.TEXT_GENERATION)


@override_settings(**DEV, VORNEQ_AI_IMAGE_ENABLED=True, VORNEQ_AI_VOICE_ENABLED=True)
class GatewayResolutionTests(SimpleTestCase):
    def test_resolution_is_metadata_not_authorization(self):
        result = resolve(Capability.TEXT_GENERATION, actor=7, environment="development",
                         provider_id="openai-text", ledger_bound=False)
        self.assertIsInstance(result, Resolution)
        self.assertTrue(result.paid)
        self.assertFalse(result.authorizes_paid_call)
        with self.assertRaises(UnauthorizedPaidCall):
            require_authorized_paid_call("text")

    def test_invalid_and_mismatched_environment(self):
        for env in ("", "test", "prod", None, "staging"):
            with self.subTest(env=env), self.assertRaises(reg.InvalidEnvironment):
                resolve(Capability.VOICE_MOCK, actor=None, environment=env, provider_id="mock-voice")

    def test_emergency_stop_blocks_every_capability(self):
        with override_settings(VORNEQ_AI_EMERGENCY_STOP=True):
            for capability, pid in ((Capability.TEXT_GENERATION, "openai-text"),
                                    (Capability.IMAGE_GENERATION, "mock-image"),
                                    (Capability.VOICE_MOCK, "mock-voice")):
                with self.subTest(pid), self.assertRaises(reg.EmergencyStopActive):
                    resolve(capability, actor=7, environment="development", provider_id=pid, ledger_bound=False)

    def test_actor_authorization_for_paid_providers(self):
        for actor in (None, 0, -1, "7", True, SimpleNamespace(is_authenticated=False, is_active=True, pk=7),
                      SimpleNamespace(is_authenticated=True, is_active=False, pk=7)):
            with self.subTest(actor=actor), self.assertRaises(reg.AuthorizationDenied):
                resolve(Capability.TEXT_GENERATION, actor=actor, environment="development",
                        provider_id="openai-text", ledger_bound=False)
        resolve(Capability.TEXT_GENERATION, actor=USER, environment="development",
                provider_id="openai-text", ledger_bound=False)

    def test_hosted_paid_resolution_requires_ledger_binding(self):
        with override_settings(**STAGING):
            for bound in (None, False, "yes"):
                with self.subTest(bound=bound), self.assertRaises(reg.BudgetRefused):
                    resolve(Capability.TEXT_GENERATION, actor=7, environment="staging",
                            provider_id="openai-text", ledger_bound=bound)
            self.assertTrue(resolve(Capability.TEXT_GENERATION, actor=7, environment="staging",
                                    provider_id="openai-text", ledger_bound=True).paid)

    def test_capability_and_model_checks(self):
        with self.assertRaises(reg.CapabilityMissing):
            resolve(Capability.IMAGE_GENERATION, actor=7, environment="development", provider_id="openai-text")
        with self.assertRaises(reg.CapabilityMissing):
            resolve(Capability.VIDEO_GENERATION, actor=7, environment="development")
        with self.assertRaises(reg.CapabilityMissing):
            resolve("text_generation", actor=7, environment="development")
        with self.assertRaises(reg.ModelUnavailable):
            resolve(Capability.IMAGE_GENERATION, actor=7, environment="development", provider_id="mock-image",
                    model_id="gpt-image-2")
        res = resolve(Capability.IMAGE_GENERATION, actor=7, environment="development",
                      provider_id="openai-image", model_id="gpt-image-2", ledger_bound=False)
        self.assertEqual(res.model.availability_status, LEGACY_POLICY)

    def test_no_silent_routing_or_fallback(self):
        with self.assertRaises(reg.InvalidConfiguration):
            resolve(Capability.IMAGE_GENERATION, actor=7, environment="development")

    def test_feature_flags(self):
        with override_settings(VORNEQ_AI_IMAGE_ENABLED=False), self.assertRaises(reg.ProviderDisabled):
            resolve(Capability.IMAGE_GENERATION, actor=7, environment="development", provider_id="mock-image")
        with override_settings(VORNEQ_AI_VOICE_ENABLED=False), self.assertRaises(reg.ProviderDisabled):
            resolve(Capability.VOICE_MOCK, actor=None, environment="development", provider_id="mock-voice")
        for gate in (False, 0, "yes"):
            with self.subTest(gate=gate), self.assertRaises(reg.ProviderDisabled):
                resolve(Capability.IMAGE_GENERATION, actor=7, environment="development",
                        provider_id="mock-image", feature_enabled=gate)
        with override_settings(VORNEQ_AI_IMAGE_ENABLED=False):
            res = resolve(Capability.IMAGE_GENERATION, actor=7, environment="development",
                          provider_id="mock-image", feature_enabled=True)
            self.assertIn("evaluated by call site", res.feature_flag)

    def test_only_user_scope_until_tenant_isolation(self):
        with self.assertRaises(reg.InvalidConfiguration):
            resolve(Capability.VOICE_MOCK, actor=None, environment="development", provider_id="mock-voice",
                    scope="organization")

    def test_legacy_text_model_only_as_configured(self):
        with mock.patch.dict(os.environ, {"VORNEQ_AI_PHASE_B_MODEL": "configured-text"}):
            res = resolve(Capability.TEXT_GENERATION, actor=7, environment="development",
                          provider_id="openai-text", model_id="configured-text", ledger_bound=False)
            self.assertEqual(res.model.availability_status, LEGACY_POLICY)
            with self.assertRaises(reg.ModelUnavailable):
                resolve(Capability.TEXT_GENERATION, actor=7, environment="development",
                        provider_id="openai-text", model_id="other", ledger_bound=False)


class LedgerBoundaryRuntimeTests(SimpleTestCase):
    def test_call_guard_rejects_missing_invalid_wrong_kind_and_expired(self):
        for bad in (None, object(), SimpleNamespace(id="x", amount_micro=1),
                    SimpleNamespace(id=uuid.uuid4(), amount_micro=0),
                    SimpleNamespace(id=uuid.uuid4(), amount_micro="1")):
            with self.subTest(bad=bad), self.assertRaises(UnauthorizedPaidCall):
                with authorized_paid_call(bad, kind="text"):
                    pass
        with self.assertRaises(UnauthorizedPaidCall), authorized_paid_call(fake_reservation(), kind="audio"):
            pass
        with authorized_paid_call(fake_reservation(), kind="image"):
            with self.assertRaises(UnauthorizedPaidCall):
                require_authorized_paid_call("text")
        with self.assertRaises(UnauthorizedPaidCall):  # nach Verlassen abgelaufen
            require_authorized_paid_call("image")

    def test_direct_provider_call_without_reservation_is_refused_before_sdk(self):
        from apps.ai_core.image_generation.providers import ImageProviderError, OpenAIImageProvider
        from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
        with mock.patch.dict(sys.modules, {"openai": None}):
            with self.assertRaises(ImageProviderError) as ctx:
                OpenAIImageProvider().generate(prompt="synthetic", model="gpt-image-2", size="1024x1024")
            self.assertFalse(ctx.exception.request_sent)
            from apps.ai_core.providers import openai_responses
            from apps.ai_core.providers.exceptions import ProviderUnavailable
            with self.assertRaises(ProviderUnavailable):
                openai_responses._require_ledger_reservation()
            self.assertTrue(callable(OpenAIResponsesProvider.generate))

    @override_settings(**STAGING)
    def test_paid_text_provider_reserves_calls_and_settles(self):
        from apps.ai_core.budgeted_provider import BudgetedProvider
        from apps.ai_core.paid_provider import paid_text_provider
        reserve, settle = start_fake_ledger(self)
        seen = []

        class Inner:
            model, max_output_tokens, instructions, last_usage = "m", 10, "i", None

            def __init__(self, **_kwargs):
                pass

            def generate(self, **_kwargs):
                seen.append(require_authorized_paid_call("text"))
                self.last_usage = (1, 1)
                return {"answer": "synthetic"}

        provider = paid_text_provider(actor_id=7, provider_class=Inner, ledger_check=lambda: True)
        self.assertIsInstance(provider, BudgetedProvider)
        provider.generate(question="q", language="en", sources=())
        self.assertEqual(len(seen), 1)
        reserve.assert_called_once()
        self.assertEqual(settle.call_args.kwargs["outcome"], "completed")

    @override_settings(**STAGING)
    def test_paid_text_resolution_refusal_keeps_http_contract(self):
        from apps.ai_core.paid_provider import paid_text_provider
        from apps.ai_ledger.service import LedgerUnavailable
        broken = Registry([provider("openai-text", enabled=False)])
        with mock.patch("apps.ai_core.provider_resolution.CATALOG", broken), \
                self.assertRaises(LedgerUnavailable):
            paid_text_provider(actor_id=7, provider_class=mock.Mock(), ledger_check=lambda: True)

    def test_image_resolution_refusal_is_provably_not_sent(self):
        from apps.ai_core.image_generation.providers import ImageProviderError
        from apps.ai_core.image_generation.service import _resolve_image_provider
        job = SimpleNamespace(owner_id=7, model_id="not-registered")
        with override_settings(**DEV, VORNEQ_AI_IMAGE_ENABLED=True), self.assertRaises(ImageProviderError) as ctx:
            _resolve_image_provider(job, "openai-image", ledger_bound=True, feature_enabled=True)
        self.assertFalse(ctx.exception.request_sent)
        self.assertEqual(ctx.exception.code, "model_unavailable")

    @override_settings(**DEV, VORNEQ_AI_VOICE_ENABLED=True, VORNEQ_AI_VOICE_PROVIDER="mock")
    def test_mocks_send_no_network_requests(self):
        import socket
        from apps.ai_core.image_generation.providers import MockImageProvider
        from apps.ai_core.voice.provider import get_provider

        def no_network(*_a, **_k):
            raise AssertionError("network access from a mock provider")

        with mock.patch.object(socket, "socket", no_network), mock.patch.object(socket, "create_connection",
                                                                                no_network), \
                mock.patch.dict(sys.modules, {"openai": None}):
            self.assertTrue(MockImageProvider().generate(prompt="synthetic", model="mock", size="1024x1024",
                                                         safety_identifier=None).is_mock)
            self.assertEqual(get_provider().respond("input_text", 3)["paid"], False)

    @override_settings(**DEV, VORNEQ_AI_VOICE_ENABLED=True)
    def test_voice_mock_cannot_become_a_real_provider(self):
        from apps.ai_core.voice.provider import VoiceProviderBlocked, get_provider
        with override_settings(VORNEQ_AI_VOICE_PROVIDER="openai"), self.assertRaises(VoiceProviderBlocked):
            get_provider()
        with override_settings(VORNEQ_AI_EMERGENCY_STOP=True), self.assertRaises(VoiceProviderBlocked):
            get_provider()


# ---------------------------------------------------------------- AST-Grenzen
CONSTRUCTED = {"OpenAIImageProvider", "MockImageProvider", "MockVoiceProvider"}
ADAPTER_FILES = {"apps/ai_core/providers/openai_responses.py", "apps/ai_core/image_generation/providers.py"}


def _runtime_files():
    for folder in ("apps", "config", "library", "marketplace", "scripts"):
        for path in (ROOT / folder).rglob("*.py"):
            rel = path.relative_to(ROOT)
            if "tests" in rel.parts or "migrations" in rel.parts or path.name.startswith("test_"):
                continue
            yield rel.as_posix(), path.read_text(encoding="utf-8-sig")


def gateway_violations(source, rel):
    """Jede Provider-Konstruktion verlangt eine vorherige Gateway-Auflösung in derselben Funktion."""
    violations = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and rel not in ADAPTER_FILES:
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(m == "openai" or m.startswith("openai.") for m in mods):
                violations.append(f"{rel}:{node.lineno}: openai SDK import outside adapters")
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = sorted((n for n in ast.walk(node) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
        resolved = False
        for call in calls:
            name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
            if name in ("resolve", "_resolve_image_provider"):
                resolved = True
            if name in CONSTRUCTED and not resolved:
                violations.append(f"{rel}:{call.lineno} {node.name}: {name}() ohne vorherige Gateway-Auflösung")
            if name == "provider_class" and rel == "apps/ai_core/paid_provider.py" and not resolved:
                violations.append(f"{rel}:{call.lineno}: provider_class() ohne vorherige Gateway-Auflösung")
    return violations


class GatewayAstBoundaryTests(SimpleTestCase):
    def test_runtime_constructions_go_through_gateway_resolution(self):
        violations, scanned = [], 0
        for rel, source in _runtime_files():
            scanned += 1
            violations += gateway_violations(source, rel)
        self.assertGreater(scanned, 100)
        self.assertEqual(violations, [])

    def test_guard_detects_violations(self):
        bad = "def f():\n    p = MockImageProvider()\n    resolve(1)\n"
        self.assertTrue(gateway_violations(bad, "apps/x.py"))
        self.assertTrue(gateway_violations("import openai\n", "apps/x.py"))
        self.assertTrue(gateway_violations("from openai import OpenAI\n", "apps/x.py"))
        ok = "def f():\n    resolve(1)\n    p = MockImageProvider()\n"
        self.assertEqual(gateway_violations(ok, "apps/x.py"), [])


class GatewayReportTests(TestCase):
    databases = "__all__"

    @override_settings(**DEV)
    def test_report_is_read_only_and_leaks_no_secrets(self):
        secrets = {"OPENAI_API_KEY": "sk-SYNTHETIC-SECRET-111", "VORNEQ_OPENAI_IMAGE_API_KEY": "sk-SYNTHETIC-222",
                   "VORNEQ_AI_PHASE_B_MODEL": "synthetic-secret-model-name"}
        out, out_json = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, secrets), mock.patch.dict(sys.modules, {"openai": None}), \
                self.assertNumQueries(0, using="default"), self.assertNumQueries(0, using="ai_ledger"):
            call_command("ai_gateway_report", stdout=out)
            call_command("ai_gateway_report", "--json", stdout=out_json)
        text = out.getvalue() + out_json.getvalue()
        for value in secrets.values():
            self.assertNotIn(value, text)
        self.assertIn("PRESENT", text)
        self.assertIn("NOT_VERIFIED", text)
        self.assertIn("A catalog entry is not an authorization", text)
        report = json.loads(out_json.getvalue())
        self.assertEqual(report["environment"], "development")
        self.assertEqual({p["provider_id"] for p in report["providers"]},
                         {"openai-text", "openai-image", "mock-image", "mock-voice"})
        self.assertEqual(report["capabilities"]["video_generation"], ["NOT_IMPLEMENTED"])
        text_provider = next(p for p in report["providers"] if p["provider_id"] == "openai-text")
        self.assertIn("ledger_reservation_at_call_boundary", text_provider["call_conditions"])
        self.assertEqual(text_provider["disabled_reasons"], [])
        mock_model = next(m for m in report["models"] if m["provider_id"] == "mock-image")
        self.assertEqual(mock_model["pricing_reference"], "NOT_APPLICABLE")
