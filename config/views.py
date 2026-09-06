"""Main views for VORNEQ."""

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.translation import get_language

from apps.core.models import ContextualReputation, Entitlement
from apps.search.services import UnifiedSearch
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


def _home_search_filters(content_type):
    if content_type == "all":
        return {}
    if content_type in {"book", "document", "other"}:
        return {"types": {"libraryitem"}, "item_type": content_type}
    if content_type == "article":
        return {"types": {"article", "libraryitem"}, "item_type": "article"}
    if content_type == "audio":
        return {"types": {"audio"}}
    if content_type == "product":
        return {"types": {"product"}}
    return {}


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

    is_unfiltered = not query and content_type == "all"
    is_first_page = requested_page == 1

    feed_items = None
    featured = []

    if is_unfiltered and is_first_page:
        cache_key = f"vorneq:home:v2:{language}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            featured = cached_payload["featured"]
            feed_items = cached_payload["feed_items"]

    if feed_items is None:
        feed_items = UnifiedSearch().collect(
            query,
            filters=_home_search_filters(content_type),
            language=language,
        )

        if is_unfiltered:
            default_featured = feed_items[:4]
            feed_items = feed_items[4:]
            if is_first_page:
                featured = default_featured
                cache.set(
                    f"vorneq:home:v2:{language}",
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
    }
    return render(request, "profile.html", context)
