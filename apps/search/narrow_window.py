from __future__ import annotations

from django.db import connection
from django.db.models import CharField, Count, F, QuerySet, Window
from django.db.models.functions import Cast
from django.urls import reverse


def supports_narrow_cte() -> bool:
    """Return whether the current backend is supported by the narrow CTE path."""
    return bool(
        connection.features.supports_over_clause
        and connection.vendor in {"postgresql", "sqlite"}
    )


def _narrow_queryset(adapter, queryset: QuerySet, limit: int) -> QuerySet:
    if limit <= 0:
        return queryset.none().values("pk")

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


def _cte_outer_bits(adapter, model) -> tuple[str, str]:
    from apps.search.services import ArticleAdapter, ProductAdapter

    qn = connection.ops.quote_name
    base_alias = "search_base"

    if isinstance(adapter, ArticleAdapter):
        field = model._meta.get_field("category")
        related = field.remote_field.model
        related_table = qn(related._meta.db_table)
        related_pk = qn(related._meta.pk.column)
        fk_column = qn(field.column)
        name_column = qn(related._meta.get_field("name").column)
        select_sql = f', search_rel.{name_column} AS "_search_category_name"'
        join_sql = (
            f" LEFT JOIN {related_table} AS search_rel"
            f" ON search_rel.{related_pk} = {base_alias}.{fk_column}"
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
        select_sql = f', search_rel.{username_column} AS "_search_seller_username"'
        join_sql = (
            f" LEFT JOIN {related_table} AS search_rel"
            f" ON search_rel.{related_pk} = {base_alias}.{fk_column}"
        )
        return select_sql, join_sql

    return "", ""


def _cte_rows(adapter, queryset: QuerySet, limit: int) -> list:
    if limit <= 0:
        return []

    inner = _narrow_queryset(adapter, queryset, limit)
    inner_sql, params = inner.query.sql_with_params()
    model = queryset.model
    qn = connection.ops.quote_name
    table = qn(model._meta.db_table)
    pk_column = qn(model._meta.pk.column)
    extra_select, extra_join = _cte_outer_bits(adapter, model)

    sql = (
        f"WITH narrow AS ({inner_sql}) "
        f'SELECT search_base.*, narrow."_search_total" AS "_search_total", '
        f'narrow."_search_published_at" AS "_search_published_at", '
        f'narrow."_search_pk_text" AS "_search_pk_text"'
        f"{extra_select} "
        f"FROM {table} AS search_base "
        f'JOIN narrow ON search_base.{pk_column} = narrow."_search_pk"'
        f"{extra_join} "
        f'ORDER BY narrow."_search_published_at" DESC, '
        f'narrow."_search_pk_text" DESC'
    )
    return list(model.objects.raw(sql, params))


def _serialize_cte(adapter, instance, *, language: str):
    from apps.search.services import ArticleAdapter, ProductAdapter, SearchResult

    if isinstance(adapter, ArticleAdapter):
        return SearchResult(
            key=f"article:{instance.pk}",
            type=adapter.type_name,
            title=instance.title,
            description=instance.summary,
            url=None,
            image_url=instance.image.url if instance.image else None,
            source="",
            published_at=instance.published_at or instance.created_at,
            category=getattr(instance, "_search_category_name", ""),
        )

    if isinstance(adapter, ProductAdapter):
        return SearchResult(
            key=f"product:{instance.pk}",
            type=adapter.type_name,
            title=instance.title,
            description=instance.short_description or instance.description,
            url=reverse("marketplace:detail", kwargs={"slug": instance.slug}),
            image_url=instance.image.url if instance.image else None,
            source=getattr(instance, "_search_seller_username", ""),
            published_at=instance.published_at or instance.created_at,
            price=instance.price,
            category=instance.category,
        )

    return adapter.serialize(instance, language=language)


def search_narrow_cte(
    search,
    query: str,
    filters: dict,
    page: int,
    page_size: int,
    *,
    language: str,
) -> dict:
    """Run exact global pagination with a narrow window-count CTE per adapter."""
    normalized_query = search.normalize_query(query)
    requested_types = search._requested_types(filters)
    candidate_limit = page * page_size

    total = 0
    candidates = []
    for adapter in search.adapters:
        if requested_types is not None and adapter.type_name not in requested_types:
            continue
        queryset = adapter.get_queryset(normalized_query, filters)
        rows = _cte_rows(adapter, queryset, candidate_limit)
        if not rows:
            continue
        total += int(rows[0]._search_total)
        candidates.extend(
            _serialize_cte(adapter, instance, language=language) for instance in rows
        )

    return search._build_page_payload(
        candidates=candidates,
        total=total,
        page=page,
        page_size=page_size,
    )
