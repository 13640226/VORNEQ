"""Offline aggregate-only Stage 2 evaluation; NEVER calls OpenAI or Render.

Input records are produced by a separately approved, budgeted Staging run.
No question, answer, passage, citation or personal data is printed or logged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

EXPECTED_LANGS = {"fa": 60, "de": 20, "en": 20}


def read_fixture(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != 100:
        raise ValueError("expected 100 public benchmark items")
    ids, langs = set(), {k: 0 for k in EXPECTED_LANGS}
    for item in data:
        if (not isinstance(item, dict) or set(item) != {"id", "language", "kind", "question"}
                or not isinstance(item["id"], str) or not isinstance(item["question"], str)
                or not 2 <= len(item["question"]) <= 200 or item["id"] in ids
                or item["language"] not in langs):
            raise ValueError("invalid benchmark fixture")
        ids.add(item["id"])
        langs[item["language"]] += 1
    if langs != EXPECTED_LANGS:
        raise ValueError("invalid language counts")
    return data


def summarize(fixture, records):
    """Trust only bounded numeric metrics, never raw model output or citations."""
    expected = {r["id"] for r in fixture}
    if not isinstance(records, list) or len(records) != 100:
        raise ValueError("one record per benchmark question required")
    seen, latencies, costs = set(), [], []
    covered = total_parts = invalid = orthography = 0
    for row in records:
        if not isinstance(row, dict) or set(row) != {
                "id", "status", "latency_ms", "observed_micro_usd",
                "covered_parts", "expected_parts", "fa_orthography_errors"
        }:
            raise ValueError("invalid aggregate metric record")
        rid = row["id"]
        if rid not in expected or rid in seen or row["status"] not in (
                "accepted", "insufficient_evidence", "rejected", "provider_error"):
            raise ValueError("duplicate or unknown metric")
        seen.add(rid)
        for key in ("latency_ms", "observed_micro_usd", "covered_parts",
                    "expected_parts", "fa_orthography_errors"):
            value = row[key]
            if type(value) is not int or not 0 <= value <= 10_000_000:
                raise ValueError("invalid numeric metric")
        if not 1 <= row["expected_parts"] <= 10 or row["covered_parts"] > row["expected_parts"]:
            raise ValueError("invalid coverage metric")
        latencies.append(row["latency_ms"])
        costs.append(row["observed_micro_usd"])
        covered += row["covered_parts"]
        total_parts += row["expected_parts"]
        orthography += row["fa_orthography_errors"]
        invalid += row["status"] != "accepted"
    if seen != expected:
        raise ValueError("missing benchmark record")
    latency_sorted = sorted(latencies)
    return {
        "samples": 100,
        "accepted": 100 - invalid,
        "accepted_pct": round((100 - invalid), 2),
        "covered_parts_pct": round(100 * covered / total_parts, 2),
        "median_latency_ms": round(median(latencies)),
        "p95_latency_ms": latency_sorted[94],
        "mean_cost_micro_usd": round(sum(costs) / len(costs)),
        "total_cost_micro_usd": sum(costs),
        "reported_orthography_errors": orthography,
        "note": "Metrics are reported by the run; no semantic truth was automatically verified.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True, help="approved local metrics-only JSON")
    args = ap.parse_args()
    fixture = read_fixture(args.fixture)
    records = json.loads(args.results.read_text(encoding="utf-8"))
    print(json.dumps(summarize(fixture, records), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
