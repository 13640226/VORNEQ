"""V7-08 Lite: Struktur des versionierten Benchmark-Seeds (keine Ausführung, keine Kosten)."""
import json
from pathlib import Path

from django.test import SimpleTestCase

SEED = Path(__file__).resolve().parents[3] / "docs" / "evaluation" / "ai-benchmark-v0.json"


class BenchmarkSeedTests(SimpleTestCase):
    def test_seed_is_versioned_balanced_and_not_claimed_as_executed(self):
        data = json.loads(SEED.read_text(encoding="utf-8"))
        self.assertEqual((data["version"], data["status"], data["thresholds"]),
                         ("0.1.0", "SEED_NOT_EXECUTED", "BASELINE_REQUIRED"))
        for metric in ("accuracy", "citation_support", "context_retention", "time_to_first_token_ms", "cost_micro_usd"):
            self.assertIn(metric, data["metrics"])
        ids = [item["id"] for item in data["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        by_language = {lang: [i for i in data["items"] if i["language"] == lang] for lang in ("fa", "de", "en")}
        self.assertEqual({len(v) for v in by_language.values()}, {len(data["items"]) // 3})
        for item in data["items"]:
            self.assertTrue(item["prompt"].strip() and item["must_include"])
            self.assertIn(item["category"], {"factual", "code", "context", "citation", "safety", "language_quality"})
