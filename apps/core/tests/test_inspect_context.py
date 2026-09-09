from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.services.context import get_context_view, resolve_artifact_from_input
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
