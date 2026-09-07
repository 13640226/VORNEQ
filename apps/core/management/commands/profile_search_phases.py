from __future__ import annotations

import json
import statistics
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils.translation import get_language

from apps.search.services import UnifiedSearch


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, int(round(fraction * len(ordered) + 0.5)) - 1),
    )
    return ordered[index]


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(_percentile(values, 0.95), 2),
        "p99_ms": round(_percentile(values, 0.99), 2),
        "avg_ms": round(statistics.fmean(values), 2),
    }


def _contract(payload: dict) -> dict:
    return {
        "keys": [item["key"] for item in payload["results"]],
        "total": payload["total"],
        "page": payload["page"],
        "total_pages": payload["total_pages"],
        "has_next": payload["has_next"],
        "has_previous": payload["has_previous"],
    }


class Command(BaseCommand):
    help = (
        "Profile UnifiedSearch. Use --interleaved to run query scenarios round-robin. "
        "Use --compare to benchmark the compatibility window-count baseline against "
        "the actual production search path with alternating execution order."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--query",
            action="append",
            dest="queries",
            help="Query to profile. Repeat the option to profile multiple queries.",
        )
        parser.add_argument("--repeat", type=int, default=5)
        parser.add_argument("--page", type=int, default=1)
        parser.add_argument("--page-size", type=int, default=UnifiedSearch.DEFAULT_PAGE_SIZE)
        parser.add_argument(
            "--interleaved",
            action="store_true",
            help="Run one sample of each query per round instead of grouping by query.",
        )
        parser.add_argument(
            "--compare",
            action="store_true",
            help=(
                "Compare the window-count baseline with the actual production path. "
                "Mode order alternates per sample to reduce order bias."
            ),
        )
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        repeat = options["repeat"]
        page = options["page"]
        page_size = options["page_size"]
        interleaved = options["interleaved"]
        compare = options["compare"]
        queries = options.get("queries") or ["", "ai", "knowledge", "science"]

        if repeat < 1:
            raise CommandError("--repeat must be at least 1")
        if page < 1:
            raise CommandError("--page must be at least 1")
        if not 1 <= page_size <= UnifiedSearch.MAX_PAGE_SIZE:
            raise CommandError(
                f"--page-size must be between 1 and {UnifiedSearch.MAX_PAGE_SIZE}"
            )

        if compare:
            self._run_comparison(
                queries=queries,
                repeat=repeat,
                page=page,
                page_size=page_size,
                interleaved=interleaved,
                as_json=options["as_json"],
            )
            return

        self._run_production(
            queries=queries,
            repeat=repeat,
            page=page,
            page_size=page_size,
            interleaved=interleaved,
            as_json=options["as_json"],
        )

    def _run_production(
        self,
        *,
        queries: list[str],
        repeat: int,
        page: int,
        page_size: int,
        interleaved: bool,
        as_json: bool,
    ) -> None:
        service = UnifiedSearch()
        measurements = [self._empty_sample(page) for _ in queries]

        def measure(query_index: int) -> None:
            raw_query = queries[query_index]
            payload, elapsed_ms, query_count = self._measure_call(
                lambda: service.search(
                    query=raw_query,
                    page=page,
                    page_size=page_size,
                )
            )
            self._record(measurements[query_index], payload, elapsed_ms, query_count)

        if interleaved:
            for _ in range(repeat):
                for query_index in range(len(queries)):
                    measure(query_index)
        else:
            for query_index in range(len(queries)):
                for _ in range(repeat):
                    measure(query_index)

        if not as_json:
            self._write_header()

        for raw_query, sample in zip(queries, measurements):
            self._write_result(
                mode="production",
                raw_query=raw_query,
                service=service,
                sample=sample,
                repeat=repeat,
                page_size=page_size,
                interleaved=interleaved,
                compare=False,
                as_json=as_json,
            )

    def _run_comparison(
        self,
        *,
        queries: list[str],
        repeat: int,
        page: int,
        page_size: int,
        interleaved: bool,
        as_json: bool,
    ) -> None:
        service = UnifiedSearch()
        language = get_language() or "en"
        modes = ("baseline", "production")
        measurements = {
            mode: [self._empty_sample(page) for _ in queries] for mode in modes
        }

        def invoke(mode: str, raw_query: str):
            if mode == "baseline":
                return service._search_with_window_count(
                    raw_query,
                    {},
                    page,
                    page_size,
                    language=language,
                )
            return service.search(
                query=raw_query,
                page=page,
                page_size=page_size,
                language=language,
            )

        def measure_pair(round_index: int, query_index: int) -> None:
            raw_query = queries[query_index]
            # Alternate which mode runs first so neither systematically benefits from
            # cache warmth or suffers from transient database drift.
            if (round_index + query_index) % 2:
                order = ("production", "baseline")
            else:
                order = ("baseline", "production")

            payloads = {}
            for mode in order:
                payload, elapsed_ms, query_count = self._measure_call(
                    lambda mode=mode: invoke(mode, raw_query)
                )
                payloads[mode] = payload
                self._record(
                    measurements[mode][query_index],
                    payload,
                    elapsed_ms,
                    query_count,
                )

            if _contract(payloads["baseline"]) != _contract(payloads["production"]):
                raise CommandError(
                    "Search contract mismatch between baseline and production for "
                    f"query={raw_query!r}, round={round_index + 1}."
                )

        if interleaved:
            for round_index in range(repeat):
                for query_index in range(len(queries)):
                    measure_pair(round_index, query_index)
        else:
            for query_index in range(len(queries)):
                for round_index in range(repeat):
                    measure_pair(round_index, query_index)

        if not as_json:
            self._write_header()

        for query_index, raw_query in enumerate(queries):
            for mode in modes:
                self._write_result(
                    mode=mode,
                    raw_query=raw_query,
                    service=service,
                    sample=measurements[mode][query_index],
                    repeat=repeat,
                    page_size=page_size,
                    interleaved=interleaved,
                    compare=True,
                    as_json=as_json,
                )

    @staticmethod
    def _empty_sample(page: int) -> dict:
        return {
            "total_ms": [],
            "query_counts": [],
            "total_results": 0,
            "resolved_page": page,
        }

    @staticmethod
    def _measure_call(callback) -> tuple[dict, float, int]:
        started = perf_counter()
        with CaptureQueriesContext(connection) as captured:
            payload = callback()
        return payload, (perf_counter() - started) * 1000, len(captured)

    @staticmethod
    def _record(sample: dict, payload: dict, elapsed_ms: float, query_count: int) -> None:
        sample["total_ms"].append(elapsed_ms)
        sample["query_counts"].append(query_count)
        sample["total_results"] = payload["total"]
        sample["resolved_page"] = payload["page"]

    def _write_header(self) -> None:
        self.stdout.write(
            "mode\tquery\trepeats\tinterleaved\tcompare\ttotal_p50_ms\t"
            "total_p95_ms\ttotal_p99_ms\tavg_db_queries\ttotal_results"
        )

    def _write_result(
        self,
        *,
        mode: str,
        raw_query: str,
        service: UnifiedSearch,
        sample: dict,
        repeat: int,
        page_size: int,
        interleaved: bool,
        compare: bool,
        as_json: bool,
    ) -> None:
        result = {
            "mode": mode,
            "query": raw_query,
            "normalized_query": service.normalize_query(raw_query),
            "repeats": repeat,
            "interleaved": interleaved,
            "compare": compare,
            "equivalent": True if compare else None,
            "page": sample["resolved_page"],
            "page_size": page_size,
            "total_results": sample["total_results"],
            "total": _summary(sample["total_ms"]),
            "avg_db_queries": round(statistics.fmean(sample["query_counts"]), 2),
        }

        if as_json:
            self.stdout.write(json.dumps(result, sort_keys=True))
            return

        self.stdout.write(
            "{mode}\t{query}\t{repeats}\t{interleaved}\t{compare}\t{p50:.2f}\t"
            "{p95:.2f}\t{p99:.2f}\t{queries:.2f}\t{results}".format(
                mode=mode,
                query=raw_query,
                repeats=repeat,
                interleaved=str(interleaved).lower(),
                compare=str(compare).lower(),
                p50=result["total"]["p50_ms"],
                p95=result["total"]["p95_ms"],
                p99=result["total"]["p99_ms"],
                queries=result["avg_db_queries"],
                results=sample["total_results"],
            )
        )
