import json
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase


class BenchmarkSearchCommandTests(TestCase):
    @patch("apps.core.management.commands.benchmark_search.UnifiedSearch.search")
    def test_json_output_reports_baseline_metrics(self, mock_search):
        mock_search.return_value = {
            "results": [],
            "total": 7,
            "page": 1,
            "total_pages": 1,
            "has_next": False,
            "has_previous": False,
        }
        stdout = StringIO()

        call_command(
            "benchmark_search",
            queries=["  Knowledge  "],
            repeat=2,
            page=1,
            page_size=12,
            as_json=True,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue().strip())
        self.assertEqual(payload["query"], "  Knowledge  ")
        self.assertEqual(payload["normalized_query"], "knowledge")
        self.assertEqual(payload["repeats"], 2)
        self.assertEqual(payload["total_results"], 7)
        self.assertIn("p50_ms", payload)
        self.assertIn("p95_ms", payload)
        self.assertIn("avg_db_queries", payload)
        self.assertEqual(mock_search.call_count, 2)

    def test_rejects_invalid_repeat(self):
        with self.assertRaisesMessage(CommandError, "--repeat must be at least 1"):
            call_command("benchmark_search", repeat=0)
