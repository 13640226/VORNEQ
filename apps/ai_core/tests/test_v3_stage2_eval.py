"""Offline-only evaluation harness contract. No network or provider usage."""
from pathlib import Path
import importlib.util

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "scripts/ai_eval_stage2.py"
SPEC = importlib.util.spec_from_file_location("_ai_eval_stage2", MODULE)
EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVAL)
FIXTURE = ROOT / "apps/ai_core/tests/fixtures/ai_eval_stage2_v1.json"


class Stage2EvalTests(SimpleTestCase):
    def test_fixture_is_fixed_60_fa_20_de_20_en(self):
        items = EVAL.read_fixture(FIXTURE)
        self.assertEqual(len(items), 100)
        self.assertEqual(len({q["id"] for q in items}), 100)
        for lang, expected in EVAL.EXPECTED_LANGS.items():
            self.assertEqual(sum(q["language"] == lang for q in items), expected)

    def test_synthetic_metrics_are_aggregate_only(self):
        items = EVAL.read_fixture(FIXTURE)
        rows = [
            {"id": q["id"], "status": "accepted", "latency_ms": 1200,
             "observed_micro_usd": 100, "covered_parts": 2,
             "expected_parts": 2, "fa_orthography_errors": 0}
            for q in items
        ]
        summary = EVAL.summarize(items, rows)
        self.assertEqual(summary["samples"], 100)
        self.assertEqual(summary["accepted"], 100)
        self.assertEqual(summary["covered_parts_pct"], 100.0)
        self.assertEqual(summary["median_latency_ms"], 1200)
        self.assertEqual(summary["p95_latency_ms"], 1200)
        self.assertEqual(summary["total_cost_micro_usd"], 10000)
        self.assertNotIn("question", summary)
        self.assertNotIn("answer", summary)

    def test_unknown_or_duplicate_ids_and_non_int_metrics_rejected(self):
        items = EVAL.read_fixture(FIXTURE)
        rows = [
            {"id": q["id"], "status": "accepted", "latency_ms": 1000,
             "observed_micro_usd": 100, "covered_parts": 1,
             "expected_parts": 1, "fa_orthography_errors": 0}
            for q in items
        ]
        rows[0]["id"] = "unknown"
        with self.assertRaises(ValueError):
            EVAL.summarize(items, rows)
        rows[0]["id"] = items[0]["id"]
        rows[0]["observed_micro_usd"] = True
        with self.assertRaises(ValueError):
            EVAL.summarize(items, rows)
