from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override

from apps.core.models import Artifact, ArtifactBinding
from apps.core.services.public_graph import PublicGraphUnavailable
from apps.core.services.registry import register_artifact
from apps.search.services import UnifiedSearch
from marketplace.models import Product


EMPTY_SEARCH_PAYLOAD = {
    "results": [],
    "total": 0,
    "page": 1,
    "total_pages": 1,
    "has_next": False,
    "has_previous": False,
}


class HomeSearchBoundaryTests(TestCase):
    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_does_not_execute_search_or_forward_advanced_filters(self, collect):
        response = self.client.get(
            reverse("home"),
            {
                "q": "Knowledge",
                "type": "product",
                "item_type": "book",
                "media_type": "image",
                "category": "ebook",
                "price_min": "1.50",
                "price_max": "9.99",
            },
        )

        self.assertEqual(response.status_code, 200)
        collect.assert_not_called()
        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'name="type"')
        self.assertNotContains(response, 'name="item_type"')
        self.assertNotContains(response, 'name="media_type"')
        self.assertNotContains(response, 'name="category"')
        self.assertNotContains(response, 'name="price_min"')
        self.assertNotContains(response, 'name="price_max"')
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, "Quick content filters")

    @patch.object(
        UnifiedSearch,
        "collect",
        return_value=[
            {
                "type": "article",
                "title": "Legacy Home result",
                "description": "Legacy result presentation",
                "url": None,
            }
        ],
    )
    def test_home_does_not_render_query_results_or_featured_feed(self, collect):
        response = self.client.get(reverse("home"), {"q": "article"})

        self.assertEqual(response.status_code, 200)
        collect.assert_not_called()
        self.assertNotContains(response, "Legacy Home result")
        self.assertNotContains(response, "Featured discovery")
        self.assertNotContains(response, "Latest Discoveries")
        self.assertNotContains(response, 'id="discoveries"')

    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_keeps_search_as_handoff_only(self, collect):
        with override("en"):
            response = self.client.get(reverse("home"))

            self.assertEqual(response.status_code, 200)
            collect.assert_not_called()
            self.assertContains(response, 'role="search"')
            self.assertContains(response, f'action="{reverse("search_page")}"')
            self.assertContains(response, "Search across VORNEQ")
            self.assertNotContains(response, "Start searching")


class StandaloneSearchPageTests(TestCase):
    @patch.object(UnifiedSearch, "search", return_value=EMPTY_SEARCH_PAYLOAD)
    def test_search_page_uses_full_allowlisted_filter_set(self, search):
        response = self.client.get(
            reverse("search_page"),
            {
                "q": "Library",
                "type": "libraryitem",
                "item_type": "document",
                "media_type": "video",
                "category": "research",
                "price_min": "2",
                "price_max": "20",
                "page": "2",
                "page_size": "999",
            },
        )

        self.assertEqual(response.status_code, 200)
        kwargs = search.call_args.kwargs
        self.assertEqual(kwargs["filters"]["types"], {"libraryitem"})
        self.assertEqual(kwargs["filters"]["item_type"], "document")
        self.assertEqual(kwargs["filters"]["media_type"], "video")
        self.assertEqual(kwargs["filters"]["category"], "research")
        self.assertEqual(kwargs["filters"]["price_min"], Decimal("2"))
        self.assertEqual(kwargs["filters"]["price_max"], Decimal("20"))
        self.assertEqual(kwargs["page"], 2)
        self.assertEqual(kwargs["page_size"], UnifiedSearch.MAX_PAGE_SIZE)

    @patch.object(UnifiedSearch, "search", return_value=EMPTY_SEARCH_PAYLOAD)
    def test_search_results_ui_stays_metadata_only(self, search):
        response = self.client.get(reverse("search_page"), {"q": "public"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "trust_score")
        self.assertNotContains(response, "contextual_reputation")
        self.assertNotContains(response, "Canonical identity")
        self.assertNotContains(response, "Verification badge")
        self.assertContains(response, 'name="type"')
        self.assertContains(response, 'name="item_type"')
        self.assertContains(response, 'name="media_type"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="price_min"')
        self.assertContains(response, 'name="price_max"')


class DiscoverV1ATests(TestCase):
    @patch.object(UnifiedSearch, "search", return_value=EMPTY_SEARCH_PAYLOAD)
    def test_discover_uses_public_retrieval_without_advanced_search_filters(self, search):
        response = self.client.get(
            reverse("discover"),
            {
                "q": "Evidence",
                "type": "libraryitem",
                "category": "ignored",
                "price_min": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        kwargs = search.call_args.kwargs
        self.assertEqual(kwargs["filters"], {"types": {"libraryitem"}})
        self.assertEqual(kwargs["query"] if "query" in kwargs else search.call_args.args[0], "evidence")
        self.assertNotContains(response, "trust_score")
        self.assertNotContains(response, "Verification badge")
        self.assertNotContains(response, 'name="category"')
        self.assertNotContains(response, 'name="price_min"')

    @patch.object(UnifiedSearch, "search", return_value=EMPTY_SEARCH_PAYLOAD)
    def test_discover_empty_query_is_recently_added_starting_point(self, search):
        with override("en"):
            response = self.client.get(reverse("discover"))

        self.assertEqual(response.status_code, 200)
        search.assert_called_once()
        self.assertContains(response, "Recently added")
        self.assertContains(response, "No connected results found.")

    @patch.object(UnifiedSearch, "search", return_value=EMPTY_SEARCH_PAYLOAD)
    def test_discover_domain_uses_verified_type_mapping(self, search):
        response = self.client.get(reverse("discover_knowledge"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            search.call_args.kwargs["filters"]["types"],
            {"article", "libraryitem", "audio"},
        )

    @patch.object(UnifiedSearch, "search", return_value=EMPTY_SEARCH_PAYLOAD)
    def test_software_services_domain_fails_closed(self, search):
        with override("en"):
            response = self.client.get(reverse("discover_software_services"))

        self.assertEqual(response.status_code, 200)
        search.assert_not_called()
        self.assertContains(response, "This discovery domain is not available yet.")


class DiscoverGraphV1AIntegrationTests(TestCase):
    def _public_product_with_artifact(self, *, active=True):
        user = get_user_model().objects.create_user(
            username=f"discover-graph-{Artifact.objects.count()}",
            password="test-pass-123",
        )
        product = Product.objects.create(
            seller=user,
            title="Discover Graph Product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        artifact, _ = register_artifact(product, created_by=user)
        if not active:
            artifact.is_active = False
            artifact.save(update_fields=["is_active"])
        return product, artifact

    def _payload(self, *, key, result_type):
        return {
            **EMPTY_SEARCH_PAYLOAD,
            "results": [{
                "key": key,
                "type": result_type,
                "title": "Public result",
                "description": "Public metadata",
                "url": "/record/",
                "image_url": None,
                "source": "",
                "published_at": None,
                "price": None,
                "category": None,
                "media_type": None,
            }],
            "total": 1,
        }

    def _graph(self, *, root_truncated=False, evidence_truncated=False):
        return {
            "root": {"type": "artifact", "ref": "00000000-0000-0000-0000-000000000001", "truncated": root_truncated},
            "nodes": [
                {"type": "evidence", "ref": "evidence-1", "truncated": evidence_truncated},
                {"type": "provenance", "ref": "p1", "source_type": "document", "timestamp": None},
            ],
            "edges": [
                {
                    "source": {"type": "artifact", "ref": "00000000-0000-0000-0000-000000000001"},
                    "target": {"type": "evidence", "ref": "evidence-1"},
                    "relation": "INCLUDES_EVIDENCE",
                },
                {
                    "source": {"type": "evidence", "ref": "evidence-1"},
                    "target": {"type": "provenance", "ref": "p1"},
                    "relation": "HAS_PROVENANCE",
                },
            ],
        }

    @patch("config.views.get_public_graph")
    @patch("config.views.Artifact.objects.filter")
    @patch.object(UnifiedSearch, "search")
    def test_product_with_existing_artifact_renders_public_graph(self, search, artifact_filter, graph):
        search.return_value = self._payload(key="product:7", result_type="product")
        artifact = MagicMock(pk="00000000-0000-0000-0000-000000000001")
        artifact_filter.return_value.only.return_value.first.return_value = artifact
        graph.return_value = self._graph(root_truncated=True, evidence_truncated=True)

        with override("en"):
            response = self.client.get(reverse("discover"), {"type": "product"})
            expected_context_url = reverse("context_view", kwargs={"artifact_id": artifact.pk})

        self.assertEqual(response.status_code, 200)
        graph.assert_called_once_with(artifact.pk)
        self.assertContains(response, "Evidence graph")
        self.assertContains(response, "Inspect context")
        self.assertContains(response, expected_context_url)
        self.assertContains(response, "INCLUDES_EVIDENCE")
        self.assertContains(response, "HAS_PROVENANCE")
        self.assertContains(response, "Additional public evidence is not shown")
        self.assertContains(response, "Additional provenance is not shown")
        self.assertNotContains(response, "trust score")
        self.assertNotContains(response, "relation_basis")

    @patch("config.views.get_public_graph")
    @patch("config.views.Artifact.objects.filter")
    @patch.object(UnifiedSearch, "search")
    def test_library_item_uses_existing_artifact_without_creation(self, search, artifact_filter, graph):
        search.return_value = self._payload(key="library:9", result_type="book")
        artifact = MagicMock(pk="00000000-0000-0000-0000-000000000002")
        artifact_filter.return_value.only.return_value.first.return_value = artifact
        graph.return_value = self._graph()

        with override("en"):
            response = self.client.get(
                reverse("discover"),
                {"type": "libraryitem"},
            )
            expected_context_url = reverse("context_view", kwargs={"artifact_id": artifact.pk})

        self.assertEqual(response.status_code, 200)
        artifact_filter.assert_called_once()
        graph.assert_called_once_with(artifact.pk)
        self.assertContains(response, "Evidence graph")
        self.assertContains(response, "Inspect context")
        self.assertContains(response, expected_context_url)

    @patch("config.views.get_public_graph")
    @patch("config.views.Artifact.objects.filter")
    @patch.object(UnifiedSearch, "search")
    def test_supported_result_without_artifact_has_no_graph_affordance(self, search, artifact_filter, graph):
        search.return_value = self._payload(key="product:7", result_type="product")
        artifact_filter.return_value.only.return_value.first.return_value = None

        with override("en"):
            response = self.client.get(reverse("discover"), {"type": "product"})

        graph.assert_not_called()
        self.assertNotContains(response, "Evidence graph")
        self.assertNotContains(response, "Inspect context")
        self.assertNotContains(response, "unverified")
        self.assertNotContains(response, "low trust")


    @patch("config.views.get_public_graph")
    @patch.object(UnifiedSearch, "search")
    def test_missing_artifact_has_no_context_handoff_or_registry_mutation(self, search, graph):
        user = get_user_model().objects.create_user(
            username="discover-context-no-artifact",
            password="test-pass-123",
        )
        product = Product.objects.create(
            seller=user,
            title="Discover Context Product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        search.return_value = self._payload(key=f"product:{product.pk}", result_type="product")
        before_artifacts = Artifact.objects.count()
        before_bindings = ArtifactBinding.objects.count()

        with override("en"):
            response = self.client.get(reverse("discover"), {"type": "product"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Inspect context")
        self.assertNotContains(response, "Evidence graph")
        self.assertEqual(Artifact.objects.count(), before_artifacts)
        self.assertEqual(ArtifactBinding.objects.count(), before_bindings)
        graph.assert_not_called()

    @patch("config.views.get_public_graph")
    @patch("config.views.Artifact.objects.filter")
    @patch.object(UnifiedSearch, "search")
    def test_public_graph_unavailable_hides_graph_affordance(self, search, artifact_filter, graph):
        search.return_value = self._payload(key="product:7", result_type="product")
        artifact = MagicMock(pk="00000000-0000-0000-0000-000000000001")
        artifact_filter.return_value.only.return_value.first.return_value = artifact
        graph.side_effect = PublicGraphUnavailable

        with override("en"):
            response = self.client.get(reverse("discover"), {"type": "product"})
            expected_context_url = reverse("context_view", kwargs={"artifact_id": artifact.pk})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Evidence graph")
        self.assertContains(response, "Inspect context")
        self.assertContains(response, expected_context_url)

    @patch("config.views.Artifact.objects.filter")
    @patch.object(UnifiedSearch, "search")
    def test_unsupported_discover_types_never_resolve_graph_artifacts(self, search, artifact_filter):
        for key, result_type in (
            ("article:1", "article"),
            ("media:2", "mediaasset"),
            ("audio:3", "audio"),
        ):
            search.return_value = self._payload(key=key, result_type=result_type)
            response = self.client.get(reverse("discover"))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Evidence graph")
            self.assertNotContains(response, "Inspect context")

        artifact_filter.assert_not_called()

    @patch("config.views.get_public_graph")
    @patch.object(UnifiedSearch, "search")
    def test_inactive_artifact_has_no_graph_affordance(self, search, graph):
        product, artifact = self._public_product_with_artifact(active=False)
        search.return_value = self._payload(key=f"product:{product.pk}", result_type="product")
        before_artifacts = Artifact.objects.count()
        before_bindings = ArtifactBinding.objects.count()

        with override("en"):
            response = self.client.get(reverse("discover"), {"type": "product"})

        self.assertEqual(response.status_code, 200)
        artifact.refresh_from_db()
        self.assertFalse(artifact.is_active)
        self.assertEqual(Artifact.objects.count(), before_artifacts)
        self.assertEqual(ArtifactBinding.objects.count(), before_bindings)
        graph.assert_not_called()
        self.assertNotContains(response, "Evidence graph")
        self.assertNotContains(response, "Inspect context")

    @patch.object(UnifiedSearch, "search")
    def test_discover_get_does_not_mutate_artifact_registry(self, search):
        product, artifact = self._public_product_with_artifact()
        search.return_value = self._payload(key=f"product:{product.pk}", result_type="product")
        before_artifacts = Artifact.objects.count()
        before_bindings = ArtifactBinding.objects.count()

        with override("en"):
            response = self.client.get(reverse("discover"), {"type": "product"})
            expected_context_url = reverse("context_view", kwargs={"artifact_id": artifact.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evidence graph")
        self.assertContains(response, "Inspect context")
        self.assertContains(response, expected_context_url)
        self.assertEqual(Artifact.objects.count(), before_artifacts)
        self.assertEqual(ArtifactBinding.objects.count(), before_bindings)
        self.assertTrue(Artifact.objects.filter(pk=artifact.pk, is_active=True).exists())

    @patch("config.views.get_public_graph")
    @patch("config.views.Artifact.objects.filter")
    @patch.object(UnifiedSearch, "search")
    def test_discover_graph_presentation_ignores_private_fields(self, search, artifact_filter, graph):
        search.return_value = self._payload(key="product:7", result_type="product")
        artifact = MagicMock(pk="00000000-0000-0000-0000-000000000001")
        artifact_filter.return_value.only.return_value.first.return_value = artifact
        payload = self._graph()
        payload["root"]["trust_score"] = "SECRET TRUST SCORE"
        payload["root"]["claim_text"] = "SECRET CLAIM TEXT"
        payload["nodes"][1]["canonical_id"] = "SECRET PROVENANCE UUID"
        payload["nodes"][1]["source_ref"] = "SECRET SOURCE REF"
        payload["nodes"][1]["transformation"] = "SECRET TRANSFORMATION"
        payload["nodes"][1]["note"] = "SECRET NOTE"
        payload["edges"][0]["relation_basis"] = "SECRET RELATION BASIS"
        payload["edges"][0]["count"] = 99
        graph.return_value = payload

        with override("en"):
            response = self.client.get(reverse("discover"), {"type": "product"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evidence graph")
        for secret in (
            "SECRET TRUST SCORE",
            "SECRET CLAIM TEXT",
            "SECRET PROVENANCE UUID",
            "SECRET SOURCE REF",
            "SECRET TRANSFORMATION",
            "SECRET NOTE",
            "SECRET RELATION BASIS",
        ):
            self.assertNotContains(response, secret)
        self.assertNotContains(response, ">99<", html=True)
        self.assertContains(response, "Inspect context")
        self.assertNotContains(response, "SECRET CONTEXT FIELD")


    @patch("config.views.get_public_graph")
    @patch("config.views.Artifact.objects.filter")
    @patch.object(UnifiedSearch, "search")
    def test_discover_graph_request_is_read_only_at_integration_boundary(self, search, artifact_filter, graph):
        search.return_value = self._payload(key="product:7", result_type="product")
        artifact = MagicMock(pk="00000000-0000-0000-0000-000000000001")
        artifact_filter.return_value.only.return_value.first.return_value = artifact
        graph.return_value = self._graph()

        response = self.client.get(reverse("discover"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("count", str(graph.return_value).lower())
        self.assertContains(response, "p1")
