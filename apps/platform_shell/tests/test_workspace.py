from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.platform_shell.registry import AppManifest, registry


User = get_user_model()


class WorkspaceTests(TestCase):
    def setUp(self):
        self._original_apps = dict(registry._apps)
        self.addCleanup(self._restore_registry)
        registry._apps.clear()

        self.manifest = AppManifest(
            slug="workspace-test-app",
            label="Workspace Test App",
            url_name="home",
            order=10,
            capabilities=("test_cap",),
            active_namespaces=("test",),
            route_prefix="test/",
        )
        registry.register(self.manifest)

        self.user = User.objects.create_user(username="workspace-test")
        self.client.force_login(self.user)

    def _restore_registry(self):
        registry._apps.clear()
        registry._apps.update(self._original_apps)

    def test_registry_get_returns_manifest_or_none(self):
        self.assertIs(registry.get("workspace-test-app"), self.manifest)
        self.assertIsNone(registry.get("missing"))

    def test_workspace_index_requires_login(self):
        self.client.logout()
        workspace_url = reverse("platform_shell:workspace_index")
        login_url = reverse("account_login")
        response = self.client.get(workspace_url)
        self.assertRedirects(response, f"{login_url}?next={workspace_url}")

    def test_workspace_index_renders_apps_and_workspace_action(self):
        response = self.client.get(reverse("platform_shell:workspace_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workspace Test App")
        self.assertContains(response, "Open in Workspace")
        self.assertContains(
            response,
            reverse(
                "platform_shell:workspace_app",
                kwargs={"slug": "workspace-test-app"},
            ),
        )

    def test_workspace_app_requires_valid_slug(self):
        response = self.client.get(
            reverse("platform_shell:workspace_app", kwargs={"slug": "missing"})
        )
        self.assertEqual(response.status_code, 404)

    def test_workspace_app_shows_context_and_explicit_open_action(self):
        response = self.client.get(
            reverse(
                "platform_shell:workspace_app",
                kwargs={"slug": "workspace-test-app"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workspace Test App")
        self.assertContains(response, "test_cap")
        self.assertContains(response, "test/")
        self.assertContains(response, "Open App")
        self.assertContains(response, f'href="{reverse("home")}"')

    def test_workspace_app_handles_unresolvable_url_name_neutrally(self):
        registry.register(
            AppManifest(
                slug="workspace-unresolvable-app",
                label="Workspace Unresolvable App",
                url_name="missing:route",
                order=20,
            )
        )
        response = self.client.get(
            reverse(
                "platform_shell:workspace_app",
                kwargs={"slug": "workspace-unresolvable-app"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "App does not have a launchable URL.")
        self.assertNotContains(response, ">Open App<")

    def test_workspace_preserves_registry_order_then_slug(self):
        registry.register(
            AppManifest(
                slug="workspace-earlier-app",
                label="Workspace Earlier App",
                url_name="home",
                order=5,
            )
        )
        response = self.client.get(reverse("platform_shell:workspace_index"))
        content = response.content.decode()
        self.assertLess(
            content.index("Workspace Earlier App"),
            content.index("Workspace Test App"),
        )
