from unittest import TestCase
from apps.ai_core.provider_registry import Capability, ProviderSpec, ModelSpec, Registry, CATALOG

class RegistryTests(TestCase):
    def test_catalog(self):
        self.assertTrue(CATALOG.provider("openai-text", Capability.TEXT).paid)
        self.assertFalse(CATALOG.provider("mock-voice", Capability.VOICE_MOCK).paid)

    def test_wrong_capability(self):
        with self.assertRaises(ValueError):
            CATALOG.provider("openai-text", Capability.IMAGE)

    def test_duplicate_provider(self):
        p = ProviderSpec("p", frozenset({Capability.TEXT}), True)
        with self.assertRaises(ValueError):
            Registry([p, p])

    def test_unpriced_paid_model(self):
        p = ProviderSpec("p", frozenset({Capability.TEXT}), True)
        with self.assertRaises(ValueError):
            Registry([p], [ModelSpec("m", "p", Capability.TEXT, enabled=True)])


    def test_configured_inventory_does_not_activate_paid_models(self):
        from types import SimpleNamespace
        from apps.ai_core.provider_registry import configured_models
        models = configured_models(SimpleNamespace(VORNEQ_AI_IMAGE_MODEL="image-test"),
                                   {"VORNEQ_AI_PHASE_B_MODEL": "text-test"})
        self.assertEqual(len(models), 2)
        self.assertTrue(all(not model.enabled for model in models))

    def test_unknown_model_fails_closed(self):
        from apps.ai_core.provider_registry import ModelUnavailable
        with self.assertRaises(ModelUnavailable):
            CATALOG.model("openai-text", "unknown")

    def test_legacy_model_requires_exact_approval(self):
        from apps.ai_core.provider_resolution import legacy_model_matches
        self.assertTrue(legacy_model_matches("openai-text", Capability.TEXT, "m", ("m",)))
        self.assertFalse(legacy_model_matches("openai-text", Capability.TEXT, "other", ("m",)))
        self.assertFalse(legacy_model_matches("openai-text", Capability.TEXT, "", ("",)))

    def test_image_model_allowlist(self):
        from apps.ai_core.provider_resolution import legacy_model_matches
        from apps.ai_core.provider_registry import CapabilityMissing
        self.assertTrue(legacy_model_matches("openai-image", Capability.IMAGE, "approved", {"approved"}))
        self.assertFalse(legacy_model_matches("openai-image", Capability.IMAGE, "unknown", {"approved"}))
        with self.assertRaises(CapabilityMissing):
            legacy_model_matches("openai-text", Capability.IMAGE, "approved", {"approved"})

    def test_disabled_provider(self):
        from apps.ai_core.provider_registry import ProviderDisabled
        registry = Registry([ProviderSpec("p", frozenset({Capability.TEXT}), False, enabled=False)])
        with self.assertRaises(ProviderDisabled):
            registry.provider("p", Capability.TEXT)

    def test_registered_model_resolution(self):
        from apps.ai_core.provider_resolution import resolve_registered_model
        from apps.ai_core.provider_registry import ModelDisabled, CapabilityMissing
        registry = Registry([ProviderSpec("p", frozenset({Capability.TEXT, Capability.IMAGE}), False)],
                            [ModelSpec("m", "p", Capability.TEXT, enabled=True),
                             ModelSpec("off", "p", Capability.TEXT)])
        self.assertEqual(resolve_registered_model("p", Capability.TEXT, "m", registry=registry).model_id, "m")
        with self.assertRaises(ModelDisabled):
            resolve_registered_model("p", Capability.TEXT, "off", registry=registry)
        with self.assertRaises(CapabilityMissing):
            resolve_registered_model("p", Capability.IMAGE, "m", registry=registry)

    def test_request_preflight_denies_invalid_context(self):
        from apps.ai_core.provider_resolution import resolve_request, InvalidEnvironment, AuthorizationDenied
        registry = Registry([ProviderSpec("p", frozenset({Capability.TEXT}), False)],
                            [ModelSpec("m", "p", Capability.TEXT, enabled=True)])
        kwargs = dict(actor_id=1, environment="staging", policy_check=lambda: True, registry=registry)
        self.assertEqual(resolve_request("p", Capability.TEXT, "m", **kwargs).model_id, "m")
        for override, error in [({"actor_id": True}, AuthorizationDenied),
                                ({"environment": "unknown"}, InvalidEnvironment),
                                ({"policy_check": lambda: False}, AuthorizationDenied)]:
            with self.assertRaises(error):
                resolve_request("p", Capability.TEXT, "m", **(kwargs | override))
