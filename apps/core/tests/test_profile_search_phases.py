import io
import json

from django.core.management import call_command
from django.test import TestCase

from apps.content.models import Article, Category


class ProfileSearchPhasesCommandTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Profiler")
        Article.objects.create(
            title="AI profiler article",
            summary="Knowledge profiler summary",
            content="Science profiler content",
            category=self.category,
            is_published=True,
        )

    def _run_json(self, *args):
        stdout = io.StringIO()
        call_command("profile_search_phases", *args, "--json", stdout=stdout)
        lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    def test_json_output_reports_count_fetch_merge_and_adapter_timings(self):
        rows = self._run_json("--query", "ai", "--repeat", "2")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["query"], "ai")
        self.assertEqual(row["normalized_query"], "ai")
        self.assertEqual(row["repeats"], 2)
        self.assertEqual(row["total_results"], 1)
        self.assertEqual(row["avg_count_db_queries"], 5.0)
        self.assertEqual(row["avg_fetch_db_queries"], 1.0)
        self.assertEqual(row["avg_db_queries"], 6.0)

        for phase in ("count", "fetch", "merge", "total"):
            self.assertEqual(set(row[phase]), {"p50_ms", "p95_ms", "avg_ms"})
            self.assertGreaterEqual(row[phase]["p50_ms"], 0)

        self.assertEqual(
            set(row["adapters"]),
            {"article", "product", "libraryitem", "mediaasset", "audio"},
        )
        for adapter in row["adapters"].values():
            self.assertIn("count", adapter)
            self.assertIn("fetch", adapter)

    def test_command_is_read_only(self):
        before = Article.objects.count()

        self._run_json("--query", "knowledge", "--repeat", "1")

        self.assertEqual(Article.objects.count(), before)
        article = Article.objects.get()
        self.assertEqual(article.title, "AI profiler article")
        self.assertTrue(article.is_published)
