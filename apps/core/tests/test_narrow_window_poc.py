from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.content.models import Article, Category
from apps.media.models import MediaAsset
from apps.search.narrow_window_poc import NarrowWindowPoC
from library.models import AudioItem, LibraryItem
from marketplace.models import Product


class NarrowWindowPoCTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        category = Category.objects.create(name="Research", slug="research")
        seller = get_user_model().objects.create_user(
            username="poc-seller",
            email="poc@example.com",
            password="unused-test-password",
        )

        article = Article.objects.create(
            title="Alpha article",
            summary="Alpha summary",
            content="Alpha body",
            category=category,
            is_published=True,
            published_at=now,
        )
        product = Product.objects.create(
            seller=seller,
            title="Alpha product",
            slug="alpha-product",
            short_description="Alpha short",
            description="Alpha product description",
            category=Product.CATEGORY_EBOOK,
            price="12.50",
            status=Product.STATUS_APPROVED,
            is_published=True,
            published_at=now,
        )
        library_item = LibraryItem.objects.create(
            title="Alpha library",
            slug="alpha-library",
            short_description="Alpha library summary",
            content="Alpha library body",
            author="Researcher",
            category="Research",
            item_type="article",
            is_published=True,
            published_at=now,
        )
        media = MediaAsset.objects.create(
            media_type=MediaAsset.MediaType.IMAGE,
            title="Alpha media",
            alt_text="Alpha asset",
            file="media_assets/alpha.jpg",
            mime_type="image/jpeg",
            byte_size=10,
            width=10,
            height=10,
            is_active=True,
        )
        audio = AudioItem.objects.create(
            title="Alpha audio",
            description="Alpha audio description",
            audio_file="audio/alpha.mp3",
            is_published=True,
        )

        # Keep all five surfaces on the same timestamp so the regression also
        # exercises the historical cross-adapter key tie-break.
        Article.objects.filter(pk=article.pk).update(created_at=now, published_at=now)
        Product.objects.filter(pk=product.pk).update(created_at=now, published_at=now)
        LibraryItem.objects.filter(pk=library_item.pk).update(
            created_at=now, published_at=now
        )
        MediaAsset.objects.filter(pk=media.pk).update(created_at=now)
        AudioItem.objects.filter(pk=audio.pk).update(created_at=now)

    def setUp(self):
        self.poc = NarrowWindowPoC()

    @staticmethod
    def _contract(result):
        return {
            "keys": [item["key"] for item in result["results"]],
            "total": result["total"],
            "page": result["page"],
            "total_pages": result["total_pages"],
            "has_next": result["has_next"],
            "has_previous": result["has_previous"],
        }

    def assert_scenarios_match(self, *, query="", filters=None, page=1, page_size=12):
        baseline = self.poc.baseline(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            language="en",
        )
        enrichment = self.poc.narrow_enrichment(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            language="en",
        )
        cte = self.poc.narrow_cte(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            language="en",
        )
        self.assertEqual(self._contract(enrichment), self._contract(baseline))
        self.assertEqual(self._contract(cte), self._contract(baseline))
        return baseline, enrichment, cte

    def test_exact_pagination_and_historical_ordering_match(self):
        for page in (1, 2, 999):
            self.assert_scenarios_match(page=page, page_size=2)

    def test_query_and_type_filter_match(self):
        self.assert_scenarios_match(query="alpha")
        baseline, _, _ = self.assert_scenarios_match(
            query="alpha",
            filters={"types": "article"},
        )
        self.assertEqual(baseline["total"], 1)
        self.assertEqual(baseline["results"][0]["key"].split(":", 1)[0], "article")

    def test_category_filter_match(self):
        baseline, _, _ = self.assert_scenarios_match(filters={"category": "research"})
        self.assertGreaterEqual(baseline["total"], 1)

    def test_expected_query_counts_when_all_adapters_have_candidates(self):
        with self.assertNumQueries(5):
            self.poc.baseline(page=1, page_size=12, language="en")
        with self.assertNumQueries(10):
            self.poc.narrow_enrichment(page=1, page_size=12, language="en")
        with self.assertNumQueries(5):
            self.poc.narrow_cte(page=1, page_size=12, language="en")

    def test_poc_paths_are_read_only(self):
        before = {
            "article": Article.objects.count(),
            "product": Product.objects.count(),
            "library": LibraryItem.objects.count(),
            "media": MediaAsset.objects.count(),
            "audio": AudioItem.objects.count(),
        }
        self.poc.narrow_enrichment(query="alpha", language="en")
        self.poc.narrow_cte(query="alpha", language="en")
        after = {
            "article": Article.objects.count(),
            "product": Product.objects.count(),
            "library": LibraryItem.objects.count(),
            "media": MediaAsset.objects.count(),
            "audio": AudioItem.objects.count(),
        }
        self.assertEqual(after, before)
