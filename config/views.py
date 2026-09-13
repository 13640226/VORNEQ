"""Main views for VORNEQ."""

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import get_language

from apps.core.models import ContextualReputation, Entitlement
from apps.search.services import UnifiedSearch
from apps.verification.services.activity import get_verification_activity
from marketplace.models import Product


SEARCH_TYPES = {"article", "product", "libraryitem", "mediaasset", "audio"}
SEARCH_ITEM_TYPES = {"book", "article", "document", "other"}
SEARCH_MEDIA_TYPES = {"image", "video"}


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
    """Render Home as orientation and routing, without retrieval behavior."""
    return render(request, "index.html")


def discover(request, domain=None):
    """Resolve the canonical Discover route contract without defining its product surface."""
    return render(request, "discover/placeholder.html", {"discover_domain": domain})


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
