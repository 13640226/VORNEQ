import io
import json

from django.core.management import call_command
from django.test import TestCase

from apps.content.models import Article, Category


class ProfileSearchTailCommandTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Tail Profiler")
        Article.objects.create(
            title="Tail diagnostic article",
            summary="Knowledge",
            content="Science",
            category=category,
            is_published=True,
        )

    def test_json_output_reports_production_and_adapter_timings(self):
        stdout = io.StringIO()
        call_command(
            "profile_search_tail",
            "--repeat",
            "2",
            "--page-size",
            "12",
            "--json",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["query"], "")
        self.assertEqual(payload["repeat"], 2)
        self.assertEqual(payload["total_results"], 1)
        self.assertGreaterEqual(payload["avg_db_queries"], 1.0)
        self.assertEqual(
            set(payload["adapters"]),
            {"article", "product", "libraryitem", "mediaasset", "audio"},
        )
        for phase in ("wall", "sql", "residual"):
            self.assertIn(phase, payload["production"])
            self.assertIn("p95_ms", payload["production"][phase])
            self.assertIn("p99_ms", payload["production"][phase])
        self.assertEqual(payload["explain"], {})

    def test_command_is_read_only(self):
        before = Article.objects.count()
        stdout = io.StringIO()
        call_command("profile_search_tail", "--repeat", "1", "--json", stdout=stdout)
        self.assertEqual(Article.objects.count(), before)
