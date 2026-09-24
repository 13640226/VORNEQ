from __future__ import annotations

import json
import statistics
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import CharField, Count, Window
from django.db.models.functions import Cast
from django.test.utils import CaptureQueriesContext

from apps.search.services import UnifiedSearch


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(fraction * len(ordered) + 0.5)) - 1))
    return ordered[index]


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(_percentile(values, 0.95), 2),
        "p99_ms": round(_percentile(values, 0.99), 2),
        "avg_ms": round(statistics.fmean(values), 2),
        "max_ms": round(max(values), 2),
    }


def _captured_sql_ms(captured) -> float:
    total_seconds = 0.0
    for query in captured.captured_queries:
        try:
            total_seconds += float(query.get("time") or 0.0)
        except (TypeError, ValueError):
            continue
    return total_seconds * 1000


def _candidate_queryset(adapter, queryset, limit: int):
    return (
        queryset.annotate(
            _search_total=Window(expression=Count("pk")),
            _search_published_at=adapter.global_time_expression(),
            _search_pk_text=Cast("pk", output_field=CharField()),
        )
        .order_by("-_search_published_at", "-_search_pk_text")[:limit]
    )


class Command(BaseCommand):
    help = (
        "Diagnose empty-query tail latency without changing production search. "
        "Reports client-observed wall time, backend-reported SQL time, and residual "
        "overhead; the residual is not claimed to be pure network time."
    )

    def add_arguments(self, parser):
        parser.add_argument("--repeat", type=int, default=100)
        parser.add_argument("--page-size", type=int, default=UnifiedSearch.DEFAULT_PAGE_SIZE)
        parser.add_argument("--include-explain", action="store_true")
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        repeat = options["repeat"]
        page_size = options["page_size"]
        if repeat < 1:
            raise CommandError("--repeat must be at least 1")
        if not 1 <= page_size <= UnifiedSearch.MAX_PAGE_SIZE:
            raise CommandError(
                f"--page-size must be between 1 and {UnifiedSearch.MAX_PAGE_SIZE}"
            )

        service = UnifiedSearch()
        adapter_samples = {
            adapter.type_name: {"wall_ms": [], "sql_ms": [], "residual_ms": [], "rows": []}
            for adapter in service.adapters
        }
        production_wall_ms: list[float] = []
        production_sql_ms: list[float] = []
        production_residual_ms: list[float] = []
        production_query_counts: list[int] = []
        total_results = 0

        for _ in range(repeat):
            for adapter in service.adapters:
                queryset = adapter.get_queryset("", {})
                started = perf_counter()
                with CaptureQueriesContext(connection) as captured:
                    rows = adapter.window_count_candidates(queryset, page_size)
                wall_ms = (perf_counter() - started) * 1000
                sql_ms = _captured_sql_ms(captured)
                sample = adapter_samples[adapter.type_name]
                sample["wall_ms"].append(wall_ms)
                sample["sql_ms"].append(sql_ms)
                sample["residual_ms"].append(max(0.0, wall_ms - sql_ms))
                sample["rows"].append(len(rows))

            started = perf_counter()
            with CaptureQueriesContext(connection) as captured:
                payload = service.search(query="", page=1, page_size=page_size)
            wall_ms = (perf_counter() - started) * 1000
            sql_ms = _captured_sql_ms(captured)
            production_wall_ms.append(wall_ms)
            production_sql_ms.append(sql_ms)
            production_residual_ms.append(max(0.0, wall_ms - sql_ms))
            production_query_counts.append(len(captured))
            total_results = payload["total"]

        adapters = {}
        for name, sample in adapter_samples.items():
            adapters[name] = {
                "wall": _summary(sample["wall_ms"]),
                "sql": _summary(sample["sql_ms"]),
                "residual": _summary(sample["residual_ms"]),
                "avg_candidate_rows": round(statistics.fmean(sample["rows"]), 2),
            }

        plans = {}
        if options["include_explain"]:
            for adapter in service.adapters:
                queryset = adapter.get_queryset("", {})
                candidate_qs = _candidate_queryset(adapter, queryset, page_size)
                if connection.vendor == "postgresql":
                    plans[adapter.type_name] = json.loads(candidate_qs.explain(format="json"))
                else:
                    plans[adapter.type_name] = candidate_qs.explain()

        result = {
            "query": "",
            "repeat": repeat,
            "page_size": page_size,
            "total_results": total_results,
            "avg_db_queries": round(statistics.fmean(production_query_counts), 2),
            "production": {
                "wall": _summary(production_wall_ms),
                "sql": _summary(production_sql_ms),
                "residual": _summary(production_residual_ms),
            },
            "adapters": adapters,
            "explain": plans,
            "notes": {
                "sql_ms": "Sum of Django backend-reported query durations.",
                "residual_ms": "Client wall time minus reported SQL time; includes Python/driver/round-trip overhead and is not pure network time.",
                "explain": "EXPLAIN only; ANALYZE is intentionally disabled to keep diagnostics read-only and low-impact.",
            },
        }

        if options["as_json"]:
            self.stdout.write(json.dumps(result, sort_keys=True))
            return

        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
