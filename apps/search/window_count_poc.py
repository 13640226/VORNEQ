from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from django.core.paginator import Paginator
from django.db.models import CharField, Count, Window
from django.db.models.functions import Cast
from django.utils.translation import get_language

from apps.search.services import SearchResult, UnifiedSearch


@dataclass(frozen=True)
class WindowSearchProfile:
    payload: dict
    query_phase_ms: float
    merge_ms: float
    adapter_ms: dict[str, float]


def window_count_search_poc(
    service: UnifiedSearch,
    query: str = "",
    filters: dict | None = None,
    page: int = 1,
    page_size: int = UnifiedSearch.DEFAULT_PAGE_SIZE,
    *,
    language: str | None = None,
) -> WindowSearchProfile:
    """Experimental one-query-per-adapter search path.

    This function is intentionally separate from ``UnifiedSearch.search()``. It
    combines each adapter's exact count with bounded candidate retrieval using
    ``COUNT(*) OVER()``. It exists only for feasibility profiling until staging
    data proves that the reduced round-trip count is a net win.

    Invalid/non-positive page values fall back to the production path because
    Django's historical ``Paginator.get_page()`` semantics resolve them to the
    last page, which cannot be known before an exact total is available.
    """

    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = service.DEFAULT_PAGE_SIZE
    page_size = min(max(1, page_size), service.MAX_PAGE_SIZE)

    try:
        requested_page = int(page)
    except (TypeError, ValueError):
        requested_page = 0

    if requested_page <= 0:
        started = perf_counter()
        payload = service.search(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            language=language,
        )
        elapsed = (perf_counter() - started) * 1000
        return WindowSearchProfile(
            payload=payload,
            query_phase_ms=elapsed,
            merge_ms=0.0,
            adapter_ms={},
        )

    normalized_query = service.normalize_query(query)
    filters = filters or {}
    language = language or get_language() or "en"
    requested_types = service._requested_types(filters)
    candidate_limit = requested_page * page_size

    candidates: list[SearchResult] = []
    total = 0
    adapter_ms: dict[str, float] = {}

    query_phase_started = perf_counter()
    for adapter in service.adapters:
        if requested_types is not None and adapter.type_name not in requested_types:
            continue

        queryset = adapter.get_queryset(normalized_query, filters)
        adapter_started = perf_counter()
        rows = list(
            queryset.annotate(
                _search_total=Window(expression=Count("pk")),
                _search_published_at=adapter.global_time_expression(),
                _search_pk_text=Cast("pk", output_field=CharField()),
            )
            .order_by("-_search_published_at", "-_search_pk_text")[:candidate_limit]
        )
        adapter_ms[adapter.type_name] = (perf_counter() - adapter_started) * 1000

        if rows:
            total += int(rows[0]._search_total)
            candidates.extend(
                adapter.serialize(instance, language=language) for instance in rows
            )

    query_phase_ms = (perf_counter() - query_phase_started) * 1000

    paginator = Paginator(range(total), page_size)
    page_obj = paginator.get_page(page)
    resolved_page = page_obj.number

    merge_started = perf_counter()
    candidates.sort(key=lambda item: (item.published_at, item.key), reverse=True)
    start = (resolved_page - 1) * page_size
    end = start + page_size
    page_results = [item.as_dict() for item in candidates[start:end]]
    merge_ms = (perf_counter() - merge_started) * 1000

    return WindowSearchProfile(
        payload={
            "results": page_results,
            "total": total,
            "page": resolved_page,
            "total_pages": paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        },
        query_phase_ms=query_phase_ms,
        merge_ms=merge_ms,
        adapter_ms=adapter_ms,
    )
