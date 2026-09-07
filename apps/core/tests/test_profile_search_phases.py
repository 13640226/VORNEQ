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

    def test_json_output_reports_production_latency_and_query_count(self):
        rows = self._run_json("--query", "ai", "--repeat", "2")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["mode"], "production")
        self.assertEqual(row["query"], "ai")
        self.assertEqual(row["normalized_query"], "ai")
        self.assertEqual(row["repeats"], 2)
        self.assertFalse(row["interleaved"])
        self.assertFalse(row["compare"])
        self.assertIsNone(row["equivalent"])
        self.assertEqual(row["total_results"], 1)
        self.assertGreaterEqual(row["avg_db_queries"], 1.0)
        self.assertEqual(
            set(row["total"]),
            {"p50_ms", "p95_ms", "p99_ms", "avg_ms"},
        )
        self.assertGreaterEqual(row["total"]["p50_ms"], 0)
        self.assertGreaterEqual(row["total"]["p99_ms"], 0)

    def test_interleaved_json_output_is_reported(self):
        rows = self._run_json(
            "--query",
            "ai",
            "--query",
            "knowledge",
            "--repeat",
            "2",
            "--interleaved",
        )

        self.assertEqual([row["query"] for row in rows], ["ai", "knowledge"])
        self.assertTrue(all(row["interleaved"] for row in rows))
        self.assertTrue(all(row["repeats"] == 2 for row in rows))

    def test_compare_reports_equivalent_baseline_and_production(self):
        rows = self._run_json(
            "--query",
            "ai",
            "--query",
            "knowledge",
            "--repeat",
            "2",
            "--interleaved",
            "--compare",
        )

        self.assertEqual(len(rows), 4)
        grouped = {(row["query"], row["mode"]): row for row in rows}
        self.assertEqual(
            set(grouped),
            {
                ("ai", "baseline"),
                ("ai", "production"),
                ("knowledge", "baseline"),
                ("knowledge", "production"),
            },
        )
        for query in ("ai", "knowledge"):
            baseline = grouped[(query, "baseline")]
            production = grouped[(query, "production")]
            self.assertTrue(baseline["compare"])
            self.assertTrue(production["compare"])
            self.assertTrue(baseline["interleaved"])
            self.assertTrue(production["interleaved"])
            self.assertTrue(baseline["equivalent"])
            self.assertTrue(production["equivalent"])
            self.assertEqual(baseline["total_results"], production["total_results"])
            self.assertGreaterEqual(baseline["avg_db_queries"], 1.0)
            self.assertGreaterEqual(production["avg_db_queries"], 1.0)

    def test_command_is_read_only(self):
        before = Article.objects.count()

        self._run_json("--query", "knowledge", "--repeat", "1", "--compare")

        self.assertEqual(Article.objects.count(), before)
        article = Article.objects.get()
        self.assertEqual(article.title, "AI profiler article")
        self.assertTrue(article.is_published)
