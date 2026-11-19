"""2026-09-06 benchmark fixture public visibility regressions.

All rows are created in disposable test databases. No production data,
file-system objects, AI provider calls or fixture deletion is involved.
"""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.ai_core.gateway import retrieve_public
from apps.content.models import Article, Category
from apps.core.benchmark_visibility import (
    is_public_library_item,
    public_articles,
    public_library_items,
    public_media_assets,
)
from apps.core.services.context import _is_public_content
from apps.media.models import MediaAsset
from apps.media.similarity import MediaSimilarityService
from apps.search.services import (
    ArticleAdapter, LibraryItemAdapter, MediaAssetAdapter, UnifiedSearch,
)
from library.models import LibraryItem


class BenchmarkVisibilityShieldTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seeded = Category.objects.create(
            name="VORNEQ Benchmark", slug="vorneq-benchmark-category",
        )
        real_category = Category.objects.create(
            name="Science Reports", slug="science-reports",
        )
        cls.seed_article = Article.objects.create(
            title="Benchmark VORNEQ sample",
            slug="vorneq-benchmark-article-000000",
            summary="Benchmark seeded citation",
            content="Synthetic article",
            category=seeded, editorial_metadata={"benchmark_seed": True},
            is_published=True,
        )
        cls.seed_article_metadata = Article.objects.create(
            title="Another benchmark example",
            slug="alternate-seed-article",
            summary="Fixture metadata",
            content="Synthetic",
            category=real_category,
            editorial_metadata={"benchmark_seed": True},
            is_published=True,
        )
        cls.real_article = Article.objects.create(
            title="Benchmark methodology for climate",
            slug="real-benchmark-methodology",
            summary="A real scientific comparison",
            content="A real research source",
            category=real_category,
            is_published=True,
        )
        cls.seed_library = LibraryItem.objects.create(
            title="Benchmark library seed",
            slug="vorneq-benchmark-library-000000",
            author="VORNEQ Benchmark Seed",
            category="benchmark",
            short_description="Synthetic library entry",
            is_published=True,
            pdf_file="library/pdfs/benchmark-fixture.pdf",
        )
        cls.seed_library_author_only = LibraryItem.objects.create(
            title="A seeded library title",
            slug="seed-library-other-slug",
            author="VORNEQ Benchmark Seed",
            short_description="Hidden by author provenance",
            is_published=True,
        )
        cls.real_library = LibraryItem.objects.create(
            title="Benchmark report written by a scientist",
            slug="actual-independent-benchmark-report",
            author="Independent Researcher",
            category="benchmark",
            short_description="Legitimate discussion of benchmarking",
            is_published=True,
        )
        cls.seed_media = MediaAsset.objects.create(
            title="VORNEQ Benchmark Media 000000",
            media_type=MediaAsset.MediaType.IMAGE,
            alt_text="Synthetic benchmark media",
            file="benchmark/vorneq-benchmark-media-000000.jpg",
            mime_type="image/jpeg",
            byte_size=8, width=10, height=10,
            presentation_metadata={"benchmark_seed": True},
            is_active=True,
        )
        cls.real_media = MediaAsset.objects.create(
            title="Benchmark experiment photograph",
            media_type=MediaAsset.MediaType.IMAGE,
            alt_text="Real field research photograph",
            file="media_assets/real-field-work.jpg",
            mime_type="image/jpeg",
            byte_size=8, width=10, height=10,
            is_active=True,
        )

    def test_exact_provenance_guards_keep_legitimate_benchmark_material(self):
        self.assertEqual(
            list(public_articles(Article.objects.all()).values_list("pk", flat=True)),
            [self.real_article.pk],
        )
        self.assertEqual(
            set(public_library_items(LibraryItem.objects.all()).values_list("pk", flat=True)),
            {self.real_library.pk},
        )
        self.assertEqual(
            set(public_media_assets(MediaAsset.objects.all()).values_list("pk", flat=True)),
            {self.real_media.pk},
        )
        self.assertTrue(is_public_library_item(self.real_library))
        self.assertFalse(is_public_library_item(self.seed_library))
        self.assertFalse(_is_public_content(self.seed_library))
        self.assertTrue(_is_public_content(self.real_library))

    def test_search_adapters_filter_fixture_rows_before_pagination_and_counts(self):
        self.assertEqual(
            set(ArticleAdapter().get_queryset("Benchmark", {}).values_list("pk", flat=True)),
            {self.real_article.pk},
        )
        self.assertEqual(
            set(LibraryItemAdapter().get_queryset("Benchmark", {}).values_list("pk", flat=True)),
            {self.real_library.pk},
        )
        self.assertEqual(
            set(MediaAssetAdapter().get_queryset("Benchmark", {}).values_list("pk", flat=True)),
            {self.real_media.pk},
        )
        result = UnifiedSearch().search("Benchmark", {}, page=1, page_size=50)
        self.assertEqual(result["total"], 2)
        self.assertEqual(
            {r["key"] for r in result["results"]},
            {f"article:{self.real_article.pk}", f"library:{self.real_library.pk}"},
        )
        self.assertEqual(len(UnifiedSearch().collect("Benchmark")), 2)

    def test_public_api_and_discover_have_no_benchmark_seed_results(self):
        response = self.client.get(reverse("search:unified"), {"q": "Benchmark"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 2)
        self.assertTrue(all("vorneq-benchmark-" not in str(x) for x in data["results"]))
        for name in ("discover", "discover_knowledge"):
            response = self.client.get(reverse(name), {"q": "Benchmark"})
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Benchmark library seed")
            self.assertNotContains(response, "Benchmark VORNEQ sample")
            self.assertContains(response, "Benchmark report written by a scientist")

    def test_library_index_detail_and_pdf_reader_deny_seed_but_keep_real(self):
        index = self.client.get(reverse("library:index"), follow=True)
        self.assertEqual(index.status_code, 200)
        self.assertNotContains(index, "Benchmark library seed")
        self.assertNotContains(index, "A seeded library title")
        self.assertContains(index, "Benchmark report written by a scientist")
        for slug in (self.seed_library.slug, self.seed_library_author_only.slug):
            self.assertEqual(
                self.client.get(reverse("library:detail", kwargs={"slug": slug}), follow=True).status_code,
                404,
            )
            self.assertEqual(
                self.client.get(reverse("library:serve_pdf", kwargs={"slug": slug}), follow=True).status_code,
                404,
            )
        self.assertEqual(
            self.client.get(reverse("library:detail", kwargs={"slug": self.real_library.slug}), follow=True).status_code,
            200,
        )

    @patch(
        "apps.ai_core.official_public_sources.retrieve_official_public",
        return_value=(),
    )
    def test_ai_public_retrieval_cannot_cite_benchmark_seeds(self, official):
        sources = retrieve_public("Benchmark", "en")
        self.assertTrue(sources)
        keys = {source.key for source in sources}
        self.assertEqual(
            keys,
            {f"article:{self.real_article.pk}", f"library:{self.real_library.pk}"},
        )
        official.assert_called_once()

    def test_media_similarity_resolver_hides_seed_records(self):
        service = MediaSimilarityService(provider=object(), index=object())
        rows = service._resolve_results([
            (str(self.seed_media.pk), 0.99),
            (str(self.real_media.pk), 0.93),
        ])
        self.assertEqual([x["id"] for x in rows], [str(self.real_media.pk)])

    def test_all_fixture_rows_remain_unchanged_in_the_database(self):
        self.assertEqual(Article.objects.count(), 3)
        self.assertEqual(LibraryItem.objects.count(), 3)
        self.assertEqual(MediaAsset.objects.count(), 2)
        self.assertTrue(Article.objects.get(pk=self.seed_article.pk).is_published)
        self.assertTrue(LibraryItem.objects.get(pk=self.seed_library.pk).is_published)
        self.assertTrue(MediaAsset.objects.get(pk=self.seed_media.pk).is_active)
