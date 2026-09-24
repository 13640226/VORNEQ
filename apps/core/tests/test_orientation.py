from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override
from unittest.mock import patch

from apps.core.services.registry import register_artifact
from marketplace.models import Product


class PublicEvidenceOrientationV1Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="orientation-owner",
            email="orientation@example.com",
            password="test-password",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Orientation Artifact",
            slug="orientation-artifact",
            short_description="Artifact for orientation handoff tests.",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.artifact, _created = register_artifact(self.product, created_by=self.user)

    def test_orientation_is_localized_and_structurally_accessible(self):
        with override("en"):
            response = self.client.get(reverse("orientation"))
            expected_discover_url = reverse("discover")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="main-content"')
        self.assertContains(response, 'aria-labelledby="orientation-title"')
        self.assertContains(response, 'id="orientation-title"')
        self.assertContains(response, "Artifact")
        self.assertContains(response, "Evidence")
        self.assertContains(response, "Provenance")
        self.assertContains(response, "Source type")
        self.assertContains(response, "Evidence graph")
        self.assertContains(response, "Context")
        self.assertContains(response, expected_discover_url)

    def test_orientation_de_uses_translated_copy(self):
        with override("de"):
            response = self.client.get(reverse("orientation"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="de"')
        self.assertContains(response, "Evidenzvokabular")
        self.assertNotContains(response, "A short guide to the terms used across Discover")

    def test_orientation_fa_uses_rtl_translated_copy(self):
        with override("fa"):
            response = self.client.get(reverse("orientation"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="fa"')
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "واژگان شواهد")
        self.assertNotContains(response, "A short guide to the terms used across Discover")

    def test_discover_exposes_orientation_handoff(self):
        with override("en"):
            response = self.client.get(reverse("discover"))
            expected_orientation_url = reverse("orientation")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, expected_orientation_url)
        self.assertContains(response, "Evidence vocabulary")

    @patch("config.inspect_views.get_public_graph")
    def test_context_exposes_orientation_handoff_independent_of_graph(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        with override("en"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
            expected_orientation_url = reverse("orientation")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, expected_orientation_url)
        self.assertContains(response, "Evidence vocabulary")
