from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.urls import reverse
from django.utils.translation import get_language

from apps.content.models import Article
from apps.media.models import MediaAsset
from library.models import AudioItem, LibraryItem
from marketplace.models import Product


@dataclass(frozen=True)
class SearchResult:
    key: str
    type: str
    title: str
    description: str
    url: str | None
    image_url: str | None
    source: str
    published_at: object
    price: object = None
    category: str | None = None
    media_type: str | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "image_url": self.image_url,
            "source": self.source,
            "published_at": self.published_at,
            "price": self.price,
            "category": self.category,
            "media_type": self.media_type,
        }


class SearchAdapter(ABC):
    type_name: str

    @abstractmethod
    def get_queryset(self, query: str, filters: dict) -> QuerySet:
        raise NotImplementedError

    @abstractmethod
    def serialize(self, instance, *, language: str) -> SearchResult:
        raise NotImplementedError


class ArticleAdapter(SearchAdapter):
    type_name = "article"

    def get_queryset(self, query: str, filters: dict) -> QuerySet:
        qs = Article.objects.filter(is_published=True).select_related("category")
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(summary__icontains=query)
                | Q(content__icontains=query)
            )
        category = filters.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        return qs

    def serialize(self, article: Article, *, language: str) -> SearchResult:
        image_url = article.image.url if article.image else None
        return SearchResult(
            key=f"article:{article.pk}",
            type=self.type_name,
            title=article.title,
            description=article.summary,
            url=None,
            image_url=image_url,
            source="",
            published_at=article.published_at or article.created_at,
            category=article.category.name,
        )


class ProductAdapter(SearchAdapter):
    type_name = "product"

    def get_queryset(self, query: str, filters: dict) -> QuerySet:
        qs = Product.objects.filter(
            status=Product.STATUS_APPROVED,
            is_published=True,
        ).select_related("seller")
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(short_description__icontains=query)
                | Q(description__icontains=query)
                | Q(tags__icontains=query)
            )
        category = filters.get("category")
        if category:
            qs = qs.filter(category=category)
        if filters.get("price_min") not in (None, ""):
            qs = qs.filter(price__gte=filters["price_min"])
        if filters.get("price_max") not in (None, ""):
            qs = qs.filter(price__lte=filters["price_max"])
        return qs

    def serialize(self, product: Product, *, language: str) -> SearchResult:
        return SearchResult(
            key=f"product:{product.pk}",
            type=self.type_name,
            title=product.title,
            description=product.short_description or product.description,
            url=product.get_absolute_url(),
            image_url=product.image.url if product.image else None,
            source=product.seller.get_username(),
            published_at=product.published_at or product.created_at,
            price=product.price,
            category=product.category,
        )


class LibraryItemAdapter(SearchAdapter):
    type_name = "libraryitem"

    def get_queryset(self, query: str, filters: dict) -> QuerySet:
        qs = LibraryItem.objects.filter(is_published=True)
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(title_en__icontains=query)
                | Q(title_de__icontains=query)
                | Q(short_description__icontains=query)
                | Q(short_description_en__icontains=query)
                | Q(short_description_de__icontains=query)
                | Q(content__icontains=query)
                | Q(content_en__icontains=query)
                | Q(content_de__icontains=query)
                | Q(author__icontains=query)
                | Q(category__icontains=query)
            )
        item_type = filters.get("item_type")
        if item_type:
            qs = qs.filter(item_type=item_type)
        category = filters.get("category")
        if category:
            qs = qs.filter(category__icontains=category)
        return qs

    def serialize(self, item: LibraryItem, *, language: str) -> SearchResult:
        return SearchResult(
            key=f"library:{item.pk}",
            type=item.item_type,
            title=item.get_title(language),
            description=item.get_short_description(language),
            url=reverse("library:detail", kwargs={"slug": item.slug}),
            image_url=None,
            source=item.author,
            published_at=item.published_at or item.created_at,
            category=item.category or item.item_type,
        )


class MediaAssetAdapter(SearchAdapter):
    type_name = "mediaasset"

    def get_queryset(self, query: str, filters: dict) -> QuerySet:
        qs = MediaAsset.objects.filter(is_active=True)
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(alt_text__icontains=query)
                | Q(mime_type__icontains=query)
            )
        media_type = filters.get("media_type")
        if media_type:
            qs = qs.filter(media_type=media_type)
        return qs

    def serialize(self, asset: MediaAsset, *, language: str) -> SearchResult:
        return SearchResult(
            key=f"media:{asset.pk}",
            type=self.type_name,
            title=asset.title or asset.alt_text or str(asset.pk),
            description=asset.alt_text,
            url=None,
            image_url=asset.file.url if asset.file else None,
            source="",
            published_at=asset.created_at,
            media_type=asset.media_type,
        )


class AudioItemAdapter(SearchAdapter):
    """Compatibility adapter preserving the existing Home audio discovery path."""

    type_name = "audio"

    def get_queryset(self, query: str, filters: dict) -> QuerySet:
        qs = AudioItem.objects.filter(is_published=True, audio_file__isnull=False).exclude(
            audio_file=""
        )
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
        return qs

    def serialize(self, item: AudioItem, *, language: str) -> SearchResult:
        return SearchResult(
            key=f"audio:{item.pk}",
            type=self.type_name,
            title=item.title,
            description=item.description,
            url=reverse("library:audio_detail", kwargs={"pk": item.pk}),
            image_url=None,
            source="",
            published_at=item.created_at,
        )


class UnifiedSearch:
    """Retrieval-only search across public VORNEQ content surfaces.

    This service intentionally does not inspect Verification, Reputation, Evidence,
    or any trust score. Results are ordered by recency only in this foundation.
    """

    DEFAULT_PAGE_SIZE = 12
    MAX_PAGE_SIZE = 50

    def __init__(self, adapters: Iterable[SearchAdapter] | None = None):
        self.adapters = list(
            adapters
            or (
                ArticleAdapter(),
                ProductAdapter(),
                LibraryItemAdapter(),
                MediaAssetAdapter(),
                AudioItemAdapter(),
            )
        )

    @staticmethod
    def normalize_query(query: str) -> str:
        return " ".join((query or "").strip().lower().split())[:200]

    def collect(self, query: str = "", filters: dict | None = None, *, language: str | None = None) -> list[dict]:
        normalized_query = self.normalize_query(query)
        filters = filters or {}
        language = language or get_language() or "en"

        requested_types = filters.get("types")
        if isinstance(requested_types, str):
            requested_types = {requested_types}
        elif requested_types:
            requested_types = set(requested_types)
        else:
            requested_types = None

        results: list[SearchResult] = []
        for adapter in self.adapters:
            if requested_types is not None and adapter.type_name not in requested_types:
                continue
            queryset = adapter.get_queryset(normalized_query, filters)
            results.extend(
                adapter.serialize(instance, language=language) for instance in queryset
            )

        results.sort(key=lambda item: (item.published_at, item.key), reverse=True)
        return [item.as_dict() for item in results]

    def search(
        self,
        query: str = "",
        filters: dict | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        *,
        language: str | None = None,
    ) -> dict:
        try:
            page_size = int(page_size)
        except (TypeError, ValueError):
            page_size = self.DEFAULT_PAGE_SIZE
        page_size = min(max(1, page_size), self.MAX_PAGE_SIZE)

        results = self.collect(query, filters, language=language)
        paginator = Paginator(results, page_size)
        page_obj = paginator.get_page(page)
        return {
            "results": page_obj.object_list,
            "total": paginator.count,
            "page": page_obj.number,
            "total_pages": paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }
