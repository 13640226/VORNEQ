from __future__ import annotations

from dataclasses import dataclass

from django.db import connection
from django.db.models import CharField, Count, F, QuerySet, Window
from django.db.models.functions import Cast
from django.urls import reverse
from django.utils.translation import get_language

from apps.search.services import (
    ArticleAdapter,
    ProductAdapter,
    SearchAdapter,
    SearchResult,
    UnifiedSearch,
)


SCENARIO_BASELINE = "baseline"
SCENARIO_NARROW_ENRICHMENT = "narrow_enrichment"
SCENARIO_NARROW_CTE = "narrow_cte"
SCENARIOS = (
    SCENARIO_BASELINE,
    SCENARIO_NARROW_ENRICHMENT,
    SCENARIO_NARROW_CTE,
)


@dataclass(frozen=True)
class NarrowRow:
    pk: object
    total: int
    published_at: object
    pk_text: str


class NarrowWindowPoC:
    """Opt-in feasibility study for narrower window-count query shapes.

    Production search remains untouched. This class exists only so profiling and
    regression tests can compare the current production query shape against two
    experimental alternatives.
    """

    def __init__(self, search: UnifiedSearch | None = None):
        self.search = search or UnifiedSearch()

    @staticmethod
    def _narrow_queryset(
        adapter: SearchAdapter,
        queryset: QuerySet,
        limit: int,
    ) -> QuerySet:
        if limit <= 0:
            return queryset.none().values("pk")

        # values() intentionally removes select_related-only enrichment joins from
        # the candidate projection. Relation joins required by filters remain.
        return (
            queryset.order_by()
            .annotate(
                _search_total=Window(expression=Count("pk")),
                _search_published_at=adapter.global_time_expression(),
                _search_pk_text=Cast("pk", output_field=CharField()),
                _search_pk=F("pk"),
            )
            .values(
                "_search_pk",
                "_search_total",
                "_search_published_at",
                "_search_pk_text",
            )
            .order_by("-_search_published_at", "-_search_pk_text")[:limit]
        )

    @classmethod
    def _narrow_rows(
        cls,
        adapter: SearchAdapter,
        queryset: QuerySet,
        limit: int,
    ) -> list[NarrowRow]:
        return [
            NarrowRow(
                pk=row["_search_pk"],
                total=int(row["_search_total"]),
                published_at=row["_search_published_at"],
                pk_text=row["_search_pk_text"],
            )
            for row in cls._narrow_queryset(adapter, queryset, limit)
        ]

    @staticmethod
    def _cte_outer_bits(adapter: SearchAdapter, model) -> tuple[str, str]:
        """Return optional select/join SQL needed to serialize without N+1 reads."""
        qn = connection.ops.quote_name
        base_alias = "poc_base"

        if isinstance(adapter, ArticleAdapter):
            field = model._meta.get_field("category")
            related = field.remote_field.model
            related_table = qn(related._meta.db_table)
            related_pk = qn(related._meta.pk.column)
            fk_column = qn(field.column)
            name_column = qn(related._meta.get_field("name").column)
            select_sql = f', poc_rel.{name_column} AS "_poc_category_name"'
            join_sql = (
                f" LEFT JOIN {related_table} AS poc_rel"
                f" ON poc_rel.{related_pk} = {base_alias}.{fk_column}"
            )
            return select_sql, join_sql

        if isinstance(adapter, ProductAdapter):
            field = model._meta.get_field("seller")
            related = field.remote_field.model
            username_field = related._meta.get_field(related.USERNAME_FIELD)
            related_table = qn(related._meta.db_table)
            related_pk = qn(related._meta.pk.column)
            fk_column = qn(field.column)
            username_column = qn(username_field.column)
            select_sql = f', poc_rel.{username_column} AS "_poc_seller_username"'
            join_sql = (
                f" LEFT JOIN {related_table} AS poc_rel"
                f" ON poc_rel.{related_pk} = {base_alias}.{fk_column}"
            )
            return select_sql, join_sql

        return "", ""

    @classmethod
    def _cte_rows(
        cls,
        adapter: SearchAdapter,
        queryset: QuerySet,
        limit: int,
    ) -> list:
        """Fetch narrow window/count + post-limit enrichment in one SQL statement."""
        if limit <= 0:
            return []

        inner = cls._narrow_queryset(adapter, queryset, limit)
        inner_sql, params = inner.query.sql_with_params()
        model = queryset.model
        qn = connection.ops.quote_name
        table = qn(model._meta.db_table)
        pk_column = qn(model._meta.pk.column)
        extra_select, extra_join = cls._cte_outer_bits(adapter, model)

        sql = (
            f"WITH narrow AS ({inner_sql}) "
            f'SELECT poc_base.*, narrow."_search_total" AS "_search_total", '
            f'narrow."_search_published_at" AS "_search_published_at", '
            f'narrow."_search_pk_text" AS "_search_pk_text"'
            f"{extra_select} "
            f"FROM {table} AS poc_base "
            f'JOIN narrow ON poc_base.{pk_column} = narrow."_search_pk"'
            f"{extra_join} "
            f'ORDER BY narrow."_search_published_at" DESC, '
            f'narrow."_search_pk_text" DESC'
        )
        return list(model.objects.raw(sql, params))

    @staticmethod
    def _serialize_cte(
        adapter: SearchAdapter,
        instance,
        *,
        language: str,
    ) -> SearchResult:
        if isinstance(adapter, ArticleAdapter):
            image_url = instance.image.url if instance.image else None
            return SearchResult(
                key=f"article:{instance.pk}",
                type=adapter.type_name,
                title=instance.title,
                description=instance.summary,
                url=None,
                image_url=image_url,
                source="",
                published_at=instance.published_at or instance.created_at,
                category=getattr(instance, "_poc_category_name", ""),
            )

        if isinstance(adapter, ProductAdapter):
            return SearchResult(
                key=f"product:{instance.pk}",
                type=adapter.type_name,
                title=instance.title,
                description=instance.short_description or instance.description,
                url=reverse("marketplace:detail", kwargs={"slug": instance.slug}),
                image_url=instance.image.url if instance.image else None,
                source=getattr(instance, "_poc_seller_username", ""),
                published_at=instance.published_at or instance.created_at,
                price=instance.price,
                category=instance.category,
            )

        return adapter.serialize(instance, language=language)

    def _selected_querysets(self, query: str, filters: dict):
        normalized_query = self.search.normalize_query(query)
        requested_types = self.search._requested_types(filters)
        for adapter in self.search.adapters:
            if requested_types is not None and adapter.type_name not in requested_types:
                continue
            yield adapter, adapter.get_queryset(normalized_query, filters)

    @staticmethod
    def _requested_page(page) -> int:
        try:
            return int(page)
        except (TypeError, ValueError):
            return 0

    def _fallback_if_needed(
        self,
        *,
        query: str,
        filters: dict,
        page,
        page_size: int,
        language: str,
    ) -> dict | None:
        requested_page = self._requested_page(page)
        if requested_page <= 0 or not connection.features.supports_over_clause:
            return self.search._search_bounded(
                query,
                filters,
                page,
                page_size,
                language=language,
            )
        return None

    def _build_payload(
        self,
        *,
        candidates: list[SearchResult],
        total: int,
        page: int,
        page_size: int,
    ) -> dict:
        return self.search._build_page_payload(
            candidates=candidates,
            total=total,
            page=page,
            page_size=page_size,
        )

    def baseline(
        self,
        query: str = "",
        filters: dict | None = None,
        page: int = 1,
        page_size: int = UnifiedSearch.DEFAULT_PAGE_SIZE,
        *,
        language: str | None = None,
    ) -> dict:
        return self.search.search(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            language=language,
        )

    def narrow_enrichment(
        self,
        query: str = "",
        filters: dict | None = None,
        page: int = 1,
        page_size: int = UnifiedSearch.DEFAULT_PAGE_SIZE,
        *,
        language: str | None = None,
    ) -> dict:
        filters = filters or {}
        language = language or get_language() or "en"
        page_size = self.search._normalize_page_size(page_size)
        fallback = self._fallback_if_needed(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            language=language,
        )
        if fallback is not None:
            return fallback

        requested_page = self._requested_page(page)
        candidate_limit = requested_page * page_size
        total = 0
        candidates: list[SearchResult] = []

        for adapter, queryset in self._selected_querysets(query, filters):
            narrow_rows = self._narrow_rows(adapter, queryset, candidate_limit)
            if not narrow_rows:
                continue
            total += narrow_rows[0].total

            pks = [row.pk for row in narrow_rows]
            instances = list(queryset.filter(pk__in=pks))
            by_pk = {instance.pk: instance for instance in instances}
            candidates.extend(
                adapter.serialize(by_pk[row.pk], language=language)
                for row in narrow_rows
                if row.pk in by_pk
            )

        return self._build_payload(
            candidates=candidates,
            total=total,
            page=requested_page,
            page_size=page_size,
        )

    def narrow_cte(
        self,
        query: str = "",
        filters: dict | None = None,
        page: int = 1,
        page_size: int = UnifiedSearch.DEFAULT_PAGE_SIZE,
        *,
        language: str | None = None,
    ) -> dict:
        filters = filters or {}
        language = language or get_language() or "en"
        page_size = self.search._normalize_page_size(page_size)
        fallback = self._fallback_if_needed(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            language=language,
        )
        if fallback is not None:
            return fallback

        requested_page = self._requested_page(page)
        candidate_limit = requested_page * page_size
        total = 0
        candidates: list[SearchResult] = []

        for adapter, queryset in self._selected_querysets(query, filters):
            rows = self._cte_rows(adapter, queryset, candidate_limit)
            if not rows:
                continue
            total += int(rows[0]._search_total)
            candidates.extend(
                self._serialize_cte(adapter, instance, language=language)
                for instance in rows
            )

        return self._build_payload(
            candidates=candidates,
            total=total,
            page=requested_page,
            page_size=page_size,
        )

    def run(
        self,
        scenario: str,
        query: str = "",
        filters: dict | None = None,
        page: int = 1,
        page_size: int = UnifiedSearch.DEFAULT_PAGE_SIZE,
        *,
        language: str | None = None,
    ) -> dict:
        if scenario == SCENARIO_BASELINE:
            return self.baseline(query, filters, page, page_size, language=language)
        if scenario == SCENARIO_NARROW_ENRICHMENT:
            return self.narrow_enrichment(
                query, filters, page, page_size, language=language
            )
        if scenario == SCENARIO_NARROW_CTE:
            return self.narrow_cte(query, filters, page, page_size, language=language)
        raise ValueError(f"Unknown narrow-window PoC scenario: {scenario}")
