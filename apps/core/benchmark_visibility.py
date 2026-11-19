"""Public visibility rules for the 2026-09-06 benchmark content seed.

Defense in depth: only public retrieval/presentation is filtered. No fixture
rows are mutated and no authoring, administrative, or audit read is hidden.
Match the observed seed's *specific* provenance markers, not generic words
such as "Benchmark" or "VORNEQ" in legitimate documents.
"""
from django.db.models import Q

ARTICLE_SLUG_PREFIX = "vorneq-benchmark-article-"
ARTICLE_CATEGORY_SLUG = "vorneq-benchmark-category"
LIBRARY_SLUG_PREFIX = "vorneq-benchmark-library-"
LIBRARY_SEED_AUTHOR = "VORNEQ Benchmark Seed"
MEDIA_TITLE_PREFIX = "VORNEQ Benchmark Media"
MEDIA_FILE_PREFIX = "benchmark/vorneq-benchmark-media-"


def public_articles(queryset):
    """Exclude articles matching any known fixture identity signal."""
    # Subquery is intentional: negating a nullable JSON lookup directly can
    # make unrelated rows vanish under SQL three-valued NULL logic.
    fixture_ids = queryset.model._base_manager.filter(
        Q(slug__startswith=ARTICLE_SLUG_PREFIX)
        | Q(editorial_metadata__benchmark_seed=True)
        | Q(category__slug=ARTICLE_CATEGORY_SLUG)
    ).values("pk")
    return queryset.exclude(pk__in=fixture_ids)


def public_library_items(queryset):
    """Shield seed library items from all public query paths."""
    return queryset.exclude(
        Q(slug__startswith=LIBRARY_SLUG_PREFIX)
        | Q(author=LIBRARY_SEED_AUTHOR)
    )


def public_media_assets(queryset):
    """Filter known seed media even if a media search adapter is added later."""
    fixture_ids = queryset.model._base_manager.filter(
        Q(title__startswith=MEDIA_TITLE_PREFIX)
        | Q(presentation_metadata__benchmark_seed=True)
        | Q(file__startswith=MEDIA_FILE_PREFIX)
    ).values("pk")
    return queryset.exclude(pk__in=fixture_ids)


def is_public_library_item(item):
    """Pure, DB-free check for already resolved public Library artifacts."""
    return bool(
        item is not None
        and item.is_published
        and not item.slug.startswith(LIBRARY_SLUG_PREFIX)
        and item.author != LIBRARY_SEED_AUTHOR
    )
