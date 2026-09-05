"""Main views for VORNEQ."""

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import get_language

from library.models import AudioItem, LibraryItem
from marketplace.models import Product


VALID_CONTENT_TYPES = {
    "all",
    "book",
    "article",
    "document",
    "other",
    "audio",
    "product",
}


def _library_feed_item(item, language):
    """Adapt a LibraryItem to the common discovery-feed contract."""
    return {
        "key": f"library:{item.pk}",
        "type": item.item_type,
        "title": item.get_title(language),
        "description": item.get_short_description(language),
        "url": reverse("library:detail", kwargs={"slug": item.slug}),
        "image_url": None,
        "source": item.author,
        "published_at": item.published_at or item.created_at,
        "price": None,
    }


def _audio_feed_item(item):
    """Adapt an AudioItem to the common discovery-feed contract."""
    return {
        "key": f"audio:{item.pk}",
        "type": "audio",
        "title": item.title,
        "description": item.description,
        "url": reverse("library:audio_detail", kwargs={"pk": item.pk}),
        "image_url": None,
        "source": "",
        "published_at": item.created_at,
        "price": None,
    }


def _product_feed_item(item):
    """Adapt a Product to the common discovery-feed contract."""
    return {
        "key": f"product:{item.pk}",
        "type": "product",
        "title": item.title,
        "description": item.short_description or item.description,
        "url": item.get_absolute_url(),
        "image_url": item.image.url if item.image else None,
        "source": item.seller.get_username(),
        "published_at": item.published_at or item.created_at,
        "price": item.price,
    }


def _build_feed(language, query="", content_type="all"):
    """Build and normalize the public discovery feed."""
    library_items = LibraryItem.objects.filter(is_published=True)
    audio_items = (
        AudioItem.objects.filter(is_published=True, audio_file__isnull=False)
        .exclude(audio_file="")
    )
    products = Product.objects.filter(
        status=Product.STATUS_APPROVED,
        is_published=True,
    ).select_related("seller")

    if query:
        library_items = library_items.filter(
            Q(title__icontains=query)
            | Q(title_en__icontains=query)
            | Q(title_de__icontains=query)
            | Q(short_description__icontains=query)
            | Q(short_description_en__icontains=query)
            | Q(short_description_de__icontains=query)
            | Q(author__icontains=query)
            | Q(category__icontains=query)
        )
        audio_items = audio_items.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
        products = products.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(tags__icontains=query)
        )

    if content_type in {"book", "article", "document", "other"}:
        library_items = library_items.filter(item_type=content_type)
        audio_items = audio_items.none()
        products = products.none()
    elif content_type == "audio":
        library_items = library_items.none()
        products = products.none()
    elif content_type == "product":
        library_items = library_items.none()
        audio_items = audio_items.none()

    feed_items = [
        *(_library_feed_item(item, language) for item in library_items),
        *(_audio_feed_item(item) for item in audio_items),
        *(_product_feed_item(item) for item in products),
    ]
    feed_items.sort(key=lambda item: item["published_at"], reverse=True)
    return feed_items


def home(request):
    """Render the VORNEQ Discovery Home with search, filters, and pagination."""
    language = get_language() or "en"
    query = request.GET.get("q", "").strip()[:200]
    content_type = request.GET.get("type", "all").strip().lower()
    if content_type not in VALID_CONTENT_TYPES:
        content_type = "all"

    page_param = request.GET.get("page", "1").strip() or "1"
    try:
        requested_page = max(1, int(page_param))
    except (TypeError, ValueError):
        requested_page = 1

    is_unfiltered = not query and content_type == "all"
    is_first_page = requested_page == 1

    feed_items = None
    featured = []

    if is_unfiltered and is_first_page:
        cache_key = f"vorneq:home:v1:{language}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            featured = cached_payload["featured"]
            feed_items = cached_payload["feed_items"]

    if feed_items is None:
        feed_items = _build_feed(language, query, content_type)

        # Keep featured items out of the paginated default feed on every page,
        # while displaying them only on page one.
        if is_unfiltered:
            default_featured = feed_items[:4]
            feed_items = feed_items[4:]
            if is_first_page:
                featured = default_featured
                cache.set(
                    f"vorneq:home:v1:{language}",
                    {"featured": featured, "feed_items": feed_items},
                    timeout=300,
                )

    paginator = Paginator(feed_items, 12)
    page_obj = paginator.get_page(requested_page)

    context = {
        "featured": featured,
        "page_obj": page_obj,
        "results": page_obj.object_list,
        "current_type": content_type,
        "search_query": query,
        "is_filtered": bool(query or content_type != "all"),
        "total_results": paginator.count,
    }

    return render(request, "index.html", context)
