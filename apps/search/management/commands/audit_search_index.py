from __future__ import annotations

import json
import os
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.search.narrow_window import build_narrow_cte_sql
from apps.search.services import UnifiedSearch


class Command(BaseCommand):
    help = (
        "Audit production-equivalent search SQL with PostgreSQL EXPLAIN "
        "(ANALYZE, BUFFERS) in read-only transactions."
    )

    QUERY_TERMS = ("", "ai", "knowledge", "science")
    PAGE = 1
    PAGE_SIZE = 12
    OUTPUT_DIR = "audit-output"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default=self.OUTPUT_DIR)
        parser.add_argument("--timeout", type=int, default=30)

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("audit_search_index requires PostgreSQL")

        timeout_sec = options["timeout"]
        if timeout_sec <= 0:
            raise CommandError("--timeout must be a positive integer")

        output_dir = options["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        search = UnifiedSearch()
        adapters = list(search.adapters)
        index_inventory = self._get_index_inventory(adapters)
        explain_results = self._collect_explain_results(search, adapters, timeout_sec)

        report = {
            "timestamp": timezone.now().isoformat(),
            "metadata": {
                "adapters": [adapter.type_name for adapter in adapters],
                "query_terms": list(self.QUERY_TERMS),
                "page": self.PAGE,
                "page_size": self.PAGE_SIZE,
                "timeout_seconds": timeout_sec,
                "read_only": True,
                "database_vendor": connection.vendor,
                "plan_count_expected": len(adapters) * len(self.QUERY_TERMS),
            },
            "index_inventory": index_inventory,
            "explain_results": explain_results,
        }

        json_path = os.path.join(output_dir, "audit-report.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)

        md_path = os.path.join(output_dir, "summary.md")
        self._generate_markdown_summary(report, md_path)

        self.stdout.write(self.style.SUCCESS(f"JSON report: {json_path}"))
        self.stdout.write(self.style.SUCCESS(f"Markdown summary: {md_path}"))

    def _get_index_inventory(self, adapters) -> dict[str, list[dict[str, Any]]]:
        table_names = sorted(
            {adapter.get_queryset("", {}).model._meta.db_table for adapter in adapters}
        )
        inventory = {table_name: [] for table_name in table_names}

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT schemaname, tablename, indexname, indexdef
                FROM pg_indexes
                WHERE tablename = ANY(%s)
                ORDER BY schemaname, tablename, indexname
                """,
                [table_names],
            )
            for schemaname, tablename, indexname, indexdef in cursor.fetchall():
                inventory.setdefault(tablename, []).append(
                    {
                        "schemaname": schemaname,
                        "indexname": indexname,
                        "indexdef": indexdef,
                    }
                )

            cursor.execute(
                """
                SELECT schemaname, relname, indexrelname,
                       idx_scan, idx_tup_read, idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE relname = ANY(%s)
                ORDER BY schemaname, relname, indexrelname
                """,
                [table_names],
            )
            stats = {
                (row[0], row[1], row[2]): row[3:]
                for row in cursor.fetchall()
            }

        for tablename, indexes in inventory.items():
            for index in indexes:
                values = stats.get(
                    (index["schemaname"], tablename, index["indexname"])
                )
                if values is None:
                    index["idx_scan"] = None
                    index["idx_tup_read"] = None
                    index["idx_tup_fetch"] = None
                else:
                    (
                        index["idx_scan"],
                        index["idx_tup_read"],
                        index["idx_tup_fetch"],
                    ) = values
        return inventory

    def _collect_explain_results(self, search, adapters, timeout_sec: int) -> list[dict]:
        results = []
        normalized_terms = [search.normalize_query(term) for term in self.QUERY_TERMS]

        for adapter in adapters:
            self.stdout.write(f"Adapter: {adapter.type_name}")
            for term in normalized_terms:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET TRANSACTION READ ONLY")
                            cursor.execute(
                                "SET LOCAL statement_timeout = %s",
                                [f"{timeout_sec}s"],
                            )

                        queryset = adapter.get_queryset(term, {})
                        sql, params = build_narrow_cte_sql(
                            adapter, queryset, self.PAGE * self.PAGE_SIZE
                        )
                        explain_sql = (
                            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql
                        )
                        started = time.perf_counter()
                        with connection.cursor() as cursor:
                            cursor.execute(explain_sql, params)
                            plan = cursor.fetchone()[0]
                        elapsed_ms = (time.perf_counter() - started) * 1000.0

                    results.append(
                        {
                            "adapter": adapter.type_name,
                            "query_term": term,
                            "elapsed_ms": round(elapsed_ms, 3),
                            "sql": sql,
                            "params_safe": [self._safe_param(param) for param in params],
                            "explain_plan": plan,
                        }
                    )
                except Exception as exc:
                    self.stderr.write(
                        f"EXPLAIN failed for {adapter.type_name}/{term!r}: {exc}"
                    )
                    results.append(
                        {
                            "adapter": adapter.type_name,
                            "query_term": term,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )
        return results

    @staticmethod
    def _safe_param(param: Any) -> str:
        if param is None:
            return "NULL"
        if isinstance(param, bool):
            return "bool"
        if isinstance(param, str):
            return f"str(length={len(param)})"
        if isinstance(param, int):
            return "int"
        if isinstance(param, (list, tuple)):
            return f"{type(param).__name__}(length={len(param)})"
        if isinstance(param, dict):
            return f"dict(length={len(param)})"
        return type(param).__name__

    def _generate_markdown_summary(self, report: dict, output_path: str) -> None:
        metadata = report["metadata"]
        lines = [
            "# Search Index Audit Summary",
            "",
            f"**Timestamp:** {report['timestamp']}",
            "",
            "## Metadata",
            "",
            f"- Adapters: {', '.join(metadata['adapters'])}",
            f"- Query terms: {', '.join(repr(q) for q in metadata['query_terms'])}",
            f"- Page: {metadata['page']}",
            f"- Page size: {metadata['page_size']}",
            f"- Timeout: {metadata['timeout_seconds']}s",
            f"- Read-only: {metadata['read_only']}",
            "",
            "## Index Inventory",
            "",
        ]

        for table, indexes in report["index_inventory"].items():
            lines.extend(
                [
                    f"### `{table}`",
                    "",
                    "| Index | idx_scan | idx_tup_read | idx_tup_fetch |",
                    "| --- | ---: | ---: | ---: |",
                ]
            )
            for index in indexes:
                lines.append(
                    f"| `{index['indexname']}` | {index['idx_scan']} | "
                    f"{index['idx_tup_read']} | {index['idx_tup_fetch']} |"
                )
            lines.append("")
            for index in indexes:
                lines.extend(
                    [
                        f"#### `{index['indexname']}`",
                        "",
                        "```sql",
                        index["indexdef"],
                        "```",
                        "",
                    ]
                )

        lines.extend(["## EXPLAIN Results", ""])
        for result in report["explain_results"]:
            lines.append(
                f"### `{result['adapter']}` / `{result['query_term'] or '<empty>'}`"
            )
            lines.append("")
            if "error" in result:
                lines.append(
                    f"Error: `{result['error_type']}` — {result['error']}"
                )
                lines.append("")
                continue
            lines.append(f"- Wall time: {result['elapsed_ms']} ms")
            lines.append(f"- Params: {', '.join(result['params_safe']) or '<none>'}")
            lines.append("")
            lines.extend(["```sql", result["sql"], "```", ""])
            lines.extend(
                [
                    "```json",
                    json.dumps(result["explain_plan"], indent=2, default=str),
                    "```",
                    "",
                ]
            )

        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
