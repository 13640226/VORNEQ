from __future__ import annotations

import json
import math
from statistics import mean
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.search.narrow_window_poc import NarrowWindowPoC, SCENARIOS


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "avg": round(mean(values), 2) if values else 0.0,
        "p50": round(_percentile(values, 0.50), 2),
        "p95": round(_percentile(values, 0.95), 2),
        "p99": round(_percentile(values, 0.99), 2),
        "max": round(max(values), 2) if values else 0.0,
    }


class Command(BaseCommand):
    help = "Profile baseline and narrow window-count PoC scenarios."

    def add_arguments(self, parser):
        parser.add_argument("--repeat", type=int, default=100)
        parser.add_argument("--query", type=str, default="")
        parser.add_argument("--page", type=int, default=1)
        parser.add_argument("--page-size", type=int, default=12)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        repeat = options["repeat"]
        if repeat <= 0:
            raise CommandError("--repeat must be greater than zero")

        query = options["query"]
        page = options["page"]
        page_size = options["page_size"]
        poc = NarrowWindowPoC()
        report = {
            "mode": "narrow-window-poc",
            "query": query,
            "normalized_query": poc.search.normalize_query(query),
            "repeat": repeat,
            "page": page,
            "page_size": poc.search._normalize_page_size(page_size),
            "scenarios": {},
        }

        reference_keys = None
        reference_contract = None

        for scenario in SCENARIOS:
            wall_samples: list[float] = []
            sql_samples: list[float] = []
            residual_samples: list[float] = []
            query_counts: list[int] = []
            last_result = None

            for _ in range(repeat):
                with CaptureQueriesContext(connection) as captured:
                    started = perf_counter()
                    result = poc.run(
                        scenario,
                        query=query,
                        filters={},
                        page=page,
                        page_size=page_size,
                    )
                    wall_ms = (perf_counter() - started) * 1000

                sql_ms = sum(float(item.get("time") or 0.0) for item in captured) * 1000
                residual_ms = max(0.0, wall_ms - sql_ms)
                wall_samples.append(wall_ms)
                sql_samples.append(sql_ms)
                residual_samples.append(residual_ms)
                query_counts.append(len(captured))
                last_result = result

            assert last_result is not None
            keys = [item["key"] for item in last_result["results"]]
            contract = {
                "total": last_result["total"],
                "page": last_result["page"],
                "total_pages": last_result["total_pages"],
                "has_next": last_result["has_next"],
                "has_previous": last_result["has_previous"],
            }
            if reference_keys is None:
                reference_keys = keys
                reference_contract = contract
            elif keys != reference_keys or contract != reference_contract:
                raise CommandError(
                    f"Scenario {scenario} does not match baseline result semantics"
                )

            report["scenarios"][scenario] = {
                "wall_ms": _summary(wall_samples),
                "sql_ms": _summary(sql_samples),
                "residual_ms": _summary(residual_samples),
                "avg_db_queries": round(mean(query_counts), 2),
                "min_db_queries": min(query_counts),
                "max_db_queries": max(query_counts),
                "total_results": last_result["total"],
                "total_pages": last_result["total_pages"],
                "result_keys": keys,
            }

        encoded = json.dumps(report, sort_keys=True)
        if options["json"]:
            self.stdout.write(encoded)
            return

        for scenario, data in report["scenarios"].items():
            wall = data["wall_ms"]
            sql = data["sql_ms"]
            self.stdout.write(
                f"{scenario}: wall p50={wall['p50']:.2f}ms "
                f"p95={wall['p95']:.2f}ms p99={wall['p99']:.2f}ms; "
                f"sql p50={sql['p50']:.2f}ms p95={sql['p95']:.2f}ms "
                f"p99={sql['p99']:.2f}ms; queries={data['avg_db_queries']:.2f}"
            )
