from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.platform_shell.registry import (
    AppManifest,
    PLATFORM_CONTRACT_VERSION,
    PlatformRegistry,
    registry,
)


class PlatformRegistryUnitTests(SimpleTestCase):
    def test_rejects_duplicate_slugs(self):
        local_registry = PlatformRegistry()
        manifest = AppManifest(slug="demo", label="Demo", url_name="home")

        local_registry.register(manifest)

        with self.assertRaisesMessage(ValueError, "Duplicate VORNEQ app slug"):
            local_registry.register(manifest)

    def test_rejects_leading_slash_route_prefix(self):
        local_registry = PlatformRegistry()

        with self.assertRaisesMessage(ValueError, "route_prefix must be relative"):
            local_registry.register(
                AppManifest(
                    slug="demo",
                    label="Demo",
                    url_name="home",
                    route_prefix="/demo/",
                )
            )

    def test_rejects_unsupported_contract_version(self):
        local_registry = PlatformRegistry()

        with self.assertRaisesMessage(ValueError, "Unsupported VORNEQ app contract version"):
            local_registry.register(
                AppManifest(
                    slug="future",
                    label="Future",
                    url_name="home",
                    contract_version=PLATFORM_CONTRACT_VERSION + 1,
                )
            )


class InstalledPlatformAppTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_discover_and_marketplace_are_registered_in_order(self):
        slugs = [manifest.slug for manifest in registry.all()]

        self.assertIn("discover", slugs)
        self.assertIn("marketplace", slugs)
        self.assertLess(slugs.index("discover"), slugs.index("marketplace"))

    def test_marketplace_route_is_mounted_from_manifest(self):
        self.assertEqual(reverse("marketplace:index"), "/fa/marketplace/")

    def test_navigation_uses_manifest_urls(self):
        request = self.factory.get("/fa/")
        request.user = AnonymousUser()
        request.resolver_match = SimpleNamespace(url_name="home", namespace=None)

        items = registry.navigation(request)
        by_slug = {item["manifest"].slug: item for item in items}

        self.assertEqual(by_slug["discover"]["url"], reverse("home"))
        self.assertTrue(by_slug["discover"]["active"])
        self.assertEqual(by_slug["marketplace"]["url"], reverse("marketplace:index"))
