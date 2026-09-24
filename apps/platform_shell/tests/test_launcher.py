from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.platform_shell.registry import AppManifest, registry


User = get_user_model()


class LauncherTests(TestCase):
    def setUp(self):
        self._original_apps = dict(registry._apps)
        self.addCleanup(self._restore_registry)
        registry._apps.clear()

        self.manifest = AppManifest(
            slug="launcher-test-app",
            label="Launcher Test App",
            url_name="home",
            order=10,
            capabilities=("test_cap",),
        )
        registry.register(self.manifest)

        self.user = User.objects.create_user(username="launcher-test")
        self.client.force_login(self.user)

    def _restore_registry(self):
        registry._apps.clear()
        registry._apps.update(self._original_apps)

    def test_launcher_requires_login(self):
        self.client.logout()
        launcher_url = reverse("platform_shell:app_launcher")
        login_url = reverse("account_login")
        response = self.client.get(launcher_url)
        self.assertRedirects(response, f"{login_url}?next={launcher_url}")

    def test_launcher_renders_registered_app_and_resolved_launch_url(self):
        response = self.client.get(reverse("platform_shell:app_launcher"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Launcher Test App")
        self.assertContains(response, "launcher-test-app")
        self.assertContains(response, "1 capability")
        self.assertContains(response, f'href="{reverse("home")}"')

    def test_launcher_respects_registry_order_then_slug(self):
        registry.register(
            AppManifest(
                slug="launcher-another-app",
                label="Launcher Another App",
                url_name="home",
                order=5,
            )
        )
        response = self.client.get(reverse("platform_shell:app_launcher"))
        content = response.content.decode()
        self.assertLess(
            content.index("Launcher Another App"),
            content.index("Launcher Test App"),
        )

    def test_launcher_marks_unresolvable_app_as_unavailable(self):
        registry.register(
            AppManifest(
                slug="launcher-unresolvable-app",
                label="Launcher Unresolvable App",
                url_name="missing:route",
                order=20,
            )
        )
        response = self.client.get(reverse("platform_shell:app_launcher"))
        self.assertContains(response, "Launcher Unresolvable App")
        self.assertContains(response, "Launch unavailable")

    def test_launcher_exposes_client_side_search_metadata(self):
        response = self.client.get(reverse("platform_shell:app_launcher"))
        self.assertContains(response, 'data-label="launcher test app"')
        self.assertContains(response, 'data-slug="launcher-test-app"')
        self.assertContains(response, "data-app-search")
