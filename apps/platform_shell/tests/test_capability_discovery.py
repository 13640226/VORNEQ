from django.test import SimpleTestCase

from apps.platform_shell.capability_discovery import CapabilityApp, CapabilityDiscovery
from apps.platform_shell.registry import (
    AppManifest,
    PlatformRegistry,
    validate_capabilities,
)


class CapabilityDiscoveryTests(SimpleTestCase):
    def setUp(self):
        self.registry = PlatformRegistry()
        self.discovery = CapabilityDiscovery(platform_registry=self.registry)

        self.marketplace_manifest = AppManifest(
            slug="marketplace",
            label="Marketplace",
            url_name="marketplace:index",
            capabilities=("commerce.catalog", "commerce.entitlement"),
        )
        self.search_manifest = AppManifest(
            slug="search",
            label="Search",
            url_name="search:index",
            capabilities=("search_provider_v1",),
        )
        self.another_search_manifest = AppManifest(
            slug="another-search",
            label="Another Search",
            url_name="another-search:index",
            capabilities=("search_provider_v1",),
        )

    def test_validate_capabilities_accepts_legacy_identifiers(self):
        validate_capabilities(("a", "b"))
        validate_capabilities(("commerce.catalog", "commerce.entitlement"))

    def test_validate_capabilities_rejects_duplicate(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_capabilities(("dup", "dup"))

    def test_validate_capabilities_rejects_empty(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            validate_capabilities(("",))

    def test_validate_capabilities_rejects_surrounding_whitespace(self):
        with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
            validate_capabilities(("  spaced  ",))

    def test_validate_capabilities_rejects_non_string(self):
        with self.assertRaisesRegex(ValueError, "must be strings"):
            validate_capabilities((123,))

    def test_register_valid_manifest(self):
        self.registry.register(self.marketplace_manifest)

        self.assertIn("marketplace", self.registry._apps)

    def test_register_invalid_manifest_does_not_mutate_registry(self):
        invalid = AppManifest(
            slug="invalid",
            label="Invalid",
            url_name="invalid:index",
            capabilities=("dup", "dup"),
        )

        with self.assertRaises(ValueError):
            self.registry.register(invalid)

        self.assertNotIn("invalid", self.registry._apps)

    def test_capability_discovery_indexes_declaring_apps(self):
        self.registry.register(self.marketplace_manifest)
        self.registry.register(self.search_manifest)
        self.registry.register(self.another_search_manifest)

        index = self.discovery.get_all_capabilities()

        self.assertIn("commerce.catalog", index)
        self.assertIn("commerce.entitlement", index)
        self.assertIn("search_provider_v1", index)
        self.assertEqual(len(index["search_provider_v1"]), 2)
        self.assertIsInstance(index["search_provider_v1"][0], CapabilityApp)

    def test_multiple_apps_may_declare_same_capability(self):
        self.registry.register(self.search_manifest)
        self.registry.register(self.another_search_manifest)

        declaring_apps = self.discovery.get_apps_with_capability("search_provider_v1")

        self.assertEqual(len(declaring_apps), 2)
        self.assertEqual(
            {app.slug for app in declaring_apps},
            {"search", "another-search"},
        )

    def test_get_app_capabilities(self):
        self.registry.register(self.marketplace_manifest)

        capabilities = self.discovery.get_app_capabilities("marketplace")

        self.assertEqual(
            capabilities,
            ("commerce.catalog", "commerce.entitlement"),
        )

    def test_get_app_capabilities_returns_empty_tuple_for_unknown_app(self):
        self.assertEqual(self.discovery.get_app_capabilities("missing"), ())
