"""Main views for VORNEQ."""

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.core.models import ContextualReputation, Entitlement
from apps.search.services import UnifiedSearch
from apps.verification.services.activity import get_verification_activity
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
SEARCH_TYPES = {"article", "product", "libraryitem", "mediaasset", "audio"}
SEARCH_ITEM_TYPES = {"book", "article", "document", "other"}
SEARCH_MEDIA_TYPES = {"image", "video"}
HOME_QUICK_FILTERS = (
    {"value": "product", "label": _("Products")},
    {"value": "book", "label": _("Books")},
    {"value": "article", "label": _("Articles")},
    {"value": "document", "label": _("Documents")},
    {"value": "audio", "label": _("Audio")},
)


def _decimal_filter(value):
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _positive_int(value, default, *, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    parsed = max(1, parsed)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _home_search_filters(content_type, request):
    if content_type == "all":
        filters = {}
    elif content_type in {"book", "document", "other"}:
        filters = {"types": {"libraryitem"}, "item_type": content_type}
    elif content_type == "article":
        filters = {"types": {"article", "libraryitem"}, "item_type": "article"}
    elif content_type == "audio":
        filters = {"types": {"audio"}}
    elif content_type == "product":
        filters = {"types": {"product"}}
    else:
        filters = {}

    item_type = request.GET.get("item_type", "").strip().lower()
    media_type = request.GET.get("media_type", "").strip().lower()
    category = request.GET.get("category", "").strip()[:120]
    price_min = _decimal_filter(request.GET.get("price_min"))
    price_max = _decimal_filter(request.GET.get("price_max"))

    if content_type == "all" and item_type in SEARCH_ITEM_TYPES:
        filters["item_type"] = item_type
    if media_type in SEARCH_MEDIA_TYPES:
        filters["media_type"] = media_type
    if category:
        filters["category"] = category
    if price_min is not None:
        filters["price_min"] = price_min
    if price_max is not None:
        filters["price_max"] = price_max
    return filters


def _standalone_search_filters(request):
    filters = {}
    requested_type = request.GET.get("type", "").strip().lower()
    item_type = request.GET.get("item_type", "").strip().lower()
    media_type = request.GET.get("media_type", "").strip().lower()
    category = request.GET.get("category", "").strip()[:120]
    price_min = _decimal_filter(request.GET.get("price_min"))
    price_max = _decimal_filter(request.GET.get("price_max"))

    if requested_type in SEARCH_TYPES:
        filters["types"] = {requested_type}
    if item_type in SEARCH_ITEM_TYPES:
        filters["item_type"] = item_type
    if media_type in SEARCH_MEDIA_TYPES:
        filters["media_type"] = media_type
    if category:
        filters["category"] = category
    if price_min is not None:
        filters["price_min"] = price_min
    if price_max is not None:
        filters["price_max"] = price_max
    return filters


def home(request):
    """Render the VORNEQ Discovery Home with unified retrieval and pagination."""
    language = get_language() or "en"
    query = UnifiedSearch.normalize_query(request.GET.get("q", ""))
    content_type = request.GET.get("type", "all").strip().lower()
    if content_type not in VALID_CONTENT_TYPES:
        content_type = "all"

    page_param = request.GET.get("page", "1").strip() or "1"
    try:
        requested_page = max(1, int(page_param))
    except (TypeError, ValueError):
        requested_page = 1

    filters = _home_search_filters(content_type, request)
    has_advanced_filters = bool(
        request.GET.get("item_type")
        or request.GET.get("media_type")
        or request.GET.get("category")
        or request.GET.get("price_min")
        or request.GET.get("price_max")
    )
    is_unfiltered = not query and content_type == "all" and not has_advanced_filters
    is_first_page = requested_page == 1

    feed_items = None
    if is_unfiltered and is_first_page:
        cache_key = f"vorneq:home:v3:{language}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            feed_items = cached_payload["feed_items"]

    if feed_items is None:
        feed_items = UnifiedSearch().collect(
            query,
            filters=filters,
            language=language,
        )
        if is_unfiltered and is_first_page:
            cache.set(
                f"vorneq:home:v3:{language}",
                {"feed_items": feed_items},
                timeout=300,
            )

    paginator = Paginator(feed_items, 12)
    page_obj = paginator.get_page(requested_page)
    page_items = list(page_obj.object_list)
    featured = page_items[:1] if is_first_page else []
    results = page_items[1:] if featured else page_items

    context = {
        "featured": featured,
        "page_obj": page_obj,
        "results": results,
        "quick_filters": HOME_QUICK_FILTERS,
        "current_type": content_type,
        "search_query": query,
        "current_item_type": request.GET.get("item_type", "").strip().lower(),
        "current_media_type": request.GET.get("media_type", "").strip().lower(),
        "current_category": request.GET.get("category", "").strip()[:120],
        "current_price_min": request.GET.get("price_min", "").strip(),
        "current_price_max": request.GET.get("price_max", "").strip(),
        "is_filtered": bool(query or content_type != "all" or has_advanced_filters),
        "total_results": paginator.count,
    }

    return render(request, "index.html", context)


def search_page(request):
    """Render standalone advanced search without Trust-layer enrichment."""
    service = UnifiedSearch()
    query = service.normalize_query(request.GET.get("q", ""))
    filters = _standalone_search_filters(request)
    page = _positive_int(request.GET.get("page"), 1)
    page_size = _positive_int(
        request.GET.get("page_size"),
        UnifiedSearch.DEFAULT_PAGE_SIZE,
        maximum=UnifiedSearch.MAX_PAGE_SIZE,
    )
    payload = service.search(
        query,
        filters=filters,
        page=page,
        page_size=page_size,
        language=get_language() or "en",
    )
    context = {
        **payload,
        "search_query": query,
        "current_type": request.GET.get("type", "").strip().lower(),
        "current_item_type": request.GET.get("item_type", "").strip().lower(),
        "current_media_type": request.GET.get("media_type", "").strip().lower(),
        "current_category": request.GET.get("category", "").strip()[:120],
        "current_price_min": request.GET.get("price_min", "").strip(),
        "current_price_max": request.GET.get("price_max", "").strip(),
        "page_size": page_size,
    }
    return render(request, "search.html", context)


@login_required
def profile(request):
    """Render a read-only account dashboard from existing VORNEQ data."""
    products = Product.objects.filter(seller=request.user).order_by("-created_at")
    entitlements = (
        Entitlement.objects.filter(user=request.user, is_active=True)
        .select_related("product")
        .order_by("-granted_at")
    )
    reputations = (
        ContextualReputation.objects.filter(user=request.user)
        .select_related("verification_method")
        .order_by("domain", "verification_method__name")
    )

    context = {
        "profile_user": request.user,
        "seller_products": products[:8],
        "seller_product_count": products.count(),
        "entitlements": entitlements[:8],
        "entitlement_count": entitlements.count(),
        "contextual_reputations": reputations,
        "reputation_context_count": reputations.count(),
        "verification_activity": get_verification_activity(request.user),
    }
    return render(request, "profile.html", context)
