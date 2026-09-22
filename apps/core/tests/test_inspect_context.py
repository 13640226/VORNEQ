from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override
from unittest.mock import patch

from apps.core.models import ArtifactBinding
from apps.core.services.context import get_context_view, resolve_artifact_from_input
from apps.core.services.public_graph import PublicGraphUnavailable
from apps.core.services.registry import register_artifact
from marketplace.models import Product


class InspectContextV1Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="inspect-owner",
            email="inspect@example.com",
            password="test-password",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Inspectable Research Artifact",
            slug="inspectable-research-artifact",
            short_description="A public artifact used by Inspect Context V1 tests.",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.artifact, _created = register_artifact(
            self.product,
            created_by=self.user,
        )

    def test_resolves_existing_public_artifact_without_creating_records(self):
        artifact_count = type(self.artifact).objects.count()

        resolved = resolve_artifact_from_input(self.product.title)

        self.assertEqual(resolved, self.artifact)
        self.assertEqual(type(self.artifact).objects.count(), artifact_count)

    def test_resolves_artifact_slug(self):
        resolved = resolve_artifact_from_input(self.product.slug)
        self.assertEqual(resolved, self.artifact)

    def test_resolves_artifact_url(self):
        resolved = resolve_artifact_from_input(
            f"https://staging.example.test/products/{self.product.slug}/"
        )
        self.assertEqual(resolved, self.artifact)

    def test_resolves_artifact_uuid(self):
        resolved = resolve_artifact_from_input(str(self.artifact.id))
        self.assertEqual(resolved, self.artifact)

    def test_does_not_resolve_unpublished_product(self):
        hidden = Product.objects.create(
            seller=self.user,
            title="Hidden Inspect Artifact",
            slug="hidden-inspect-artifact",
            status=Product.STATUS_APPROVED,
            is_published=False,
        )
        register_artifact(hidden, created_by=self.user)

        self.assertIsNone(resolve_artifact_from_input(hidden.title))

    def test_context_projection_contains_no_global_trust_score(self):
        context = get_context_view(self.artifact.id, language="en")

        self.assertEqual(context["artifact"], self.artifact)
        self.assertEqual(context["source"]["title"], self.product.title)
        self.assertEqual(context["verification"]["total_verifications"], 0)
        self.assertNotIn("score", context)
        self.assertNotIn("trust_score", context)

    def test_context_page_is_linkable_by_artifact_uuid(self):
        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
        self.assertContains(response, str(self.artifact.id))

    def test_inspect_post_redirects_to_canonical_context_page(self):
        response = self.client.post(
            reverse("inspect_entry"),
            {"input": self.product.title},
        )

        self.assertRedirects(
            response,
            reverse("context_view", kwargs={"artifact_id": self.artifact.id}),
        )


    @patch("config.inspect_views.get_public_graph")
    def test_context_exposes_existing_public_graph_handoff_when_available(self, graph):
        graph.return_value = {
            "root": {"private_note": "SECRET GRAPH DTO"},
            "nodes": [],
            "edges": [],
        }

        with override("en"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
            expected_discover_url = reverse("discover")
        expected_url = reverse("public_graph_presentation", kwargs={"artifact_id": self.artifact.id})

        self.assertEqual(response.status_code, 200)
        graph.assert_called_once_with(self.artifact.id)
        self.assertContains(response, "Inspect Evidence Graph")
        self.assertContains(response, expected_url)
        self.assertContains(response, '<nav class="context-actions" aria-labelledby="context-title">')
        self.assertContains(response, expected_discover_url)
        self.assertNotContains(response, "SECRET GRAPH DTO")
        self.assertNotContains(response, "trust score")

    @patch("config.inspect_views.get_public_graph")
    def test_context_hides_graph_handoff_when_public_graph_is_unavailable(self, graph):
        graph.side_effect = PublicGraphUnavailable

        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Inspect Evidence Graph")
        self.assertContains(response, '<nav class="context-actions" aria-labelledby="context-title">')
        self.assertContains(response, reverse("discover"))
        self.assertNotContains(response, "unverified")
        self.assertNotContains(response, "low trust")

    @patch("config.inspect_views.get_public_graph")
    def test_context_graph_handoff_get_does_not_mutate_artifact_registry(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        before_artifacts = type(self.artifact).objects.count()
        before_bindings = ArtifactBinding.objects.count()

        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(self.artifact).objects.count(), before_artifacts)
        self.assertEqual(ArtifactBinding.objects.count(), before_bindings)


    @patch("config.inspect_views.get_public_graph")
    def test_context_page_has_single_canonical_main_and_accessible_affordances(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        with override("en"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
            expected_discover_url = reverse("discover")
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("<main"), 1)
        self.assertContains(response, '<main id="main-content"')
        self.assertNotContains(response, '<main class="container"')
        self.assertContains(response, '<div class="container" aria-labelledby="context-title">')
        self.assertContains(response, 'id="context-title"')
        self.assertContains(response, "Open source artifact")
        self.assertContains(response, "Inspect Evidence Graph")
        self.assertContains(response, '<nav class="context-actions" aria-labelledby="context-title">')
        self.assertContains(response, expected_discover_url)
        self.assertContains(response, 'aria-hidden="true"')
        self.assertContains(response, 'href="#main-content"')
        self.assertContains(response, 'type="button"')
        self.assertContains(response, 'class="global-back__button"')
        self.assertContains(response, 'aria-label="Go back to the previous page"')
        self.assertContains(response, 'class="global-back__icon" aria-hidden="true"')

    @patch("config.inspect_views.get_public_graph")
    def test_context_graph_unavailable_has_no_interactive_graph_affordance(self, graph):
        graph.side_effect = PublicGraphUnavailable
        with override("en"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
            expected_discover_url = reverse("discover")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Inspect Evidence Graph")
        self.assertContains(response, '<nav class="context-actions" aria-labelledby="context-title">')
        self.assertContains(response, expected_discover_url)



class InspectContextI18nRtlStructuralTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="inspect-i18n-owner",
            email="inspect-i18n@example.com",
            password="test-password",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Inspectable I18n Artifact",
            slug="inspectable-i18n-artifact",
            short_description="A public artifact used by Context i18n/RTL tests.",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.artifact, _created = register_artifact(
            self.product,
            created_by=self.user,
        )

    @patch("config.inspect_views.get_public_graph")
    def test_context_de_renders_translated_affordances(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        with override("de"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
        self.assertContains(response, 'lang="de"')
        self.assertContains(response, "Kontext prüfen")
        self.assertContains(response, "Evidenzgraph prüfen")
        self.assertNotContains(response, "Inspect Evidence Graph")

    @patch("config.inspect_views.get_public_graph")
    def test_context_fa_renders_rtl_translated_affordances(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        with override("fa"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
        self.assertContains(response, 'lang="fa"')
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "بررسی زمینه")
        self.assertContains(response, "بررسی گراف شواهد")
        self.assertNotContains(response, "Inspect Evidence Graph")
