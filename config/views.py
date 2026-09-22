"""Main views for VORNEQ."""

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import get_language

from apps.core.models import Artifact, ContextualReputation, Entitlement
from apps.core.services.public_graph import PublicGraphUnavailable, get_public_graph
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


DISCOVER_TYPES = {"article", "product", "libraryitem", "mediaasset", "audio"}
DISCOVER_DOMAIN_TYPES = {
    "knowledge": {"article", "libraryitem", "audio"},
    "media": {"mediaasset", "audio"},
    "products-commerce": {"product"},
}


DISCOVER_GRAPH_TARGETS = {
    "product": ("marketplace", "product"),
    "library": ("library", "libraryitem"),
}


def _discover_graph_for_result(result):
    """Return Public Graph V1 for an existing eligible Discover result, or None."""
    key = result.get("key", "")
    prefix, separator, object_id = key.partition(":")
    target = DISCOVER_GRAPH_TARGETS.get(prefix)
    if not separator or not object_id or target is None:
        return None

    artifact = (
        Artifact.objects.filter(
            binding__content_type__app_label=target[0],
            binding__content_type__model=target[1],
            binding__object_id=object_id,
            is_active=True,
        )
        .only("id")
        .first()
    )
    if artifact is None:
        return None

    try:
        return get_public_graph(artifact.pk)
    except PublicGraphUnavailable:
        return None


def _attach_discover_graphs(payload):
    """Enrich only the current public result page; never create canonical records."""
    enriched = []
    for result in payload["results"]:
        item = dict(result)
        item["public_graph"] = _discover_graph_for_result(item)
        enriched.append(item)
    return {**payload, "results": enriched}


def discover(request, domain=None):
    """Render public discovery using retrieval-only, disclosure-safe metadata."""
    service = UnifiedSearch()
    query = service.normalize_query(request.GET.get("q", ""))
    requested_type = request.GET.get("type", "").strip().lower()
    page = _positive_int(request.GET.get("page"), 1)

    filters = {}
    if requested_type in DISCOVER_TYPES:
        filters["types"] = {requested_type}
    elif domain in DISCOVER_DOMAIN_TYPES:
        filters["types"] = DISCOVER_DOMAIN_TYPES[domain]

    # software-services intentionally has no V1A retrieval mapping: Product is
    # broader than software/services, so treating all products as software would
    # invent semantics. Keep the canonical route but fail closed.
    domain_supported = domain != "software-services"
    if domain_supported:
        payload = _attach_discover_graphs(service.search(
            query,
            filters=filters,
            page=page,
            page_size=UnifiedSearch.DEFAULT_PAGE_SIZE,
            language=get_language() or "en",
        ))
    else:
        payload = {
            "results": [],
            "total": 0,
            "page": 1,
            "total_pages": 1,
            "has_next": False,
            "has_previous": False,
        }

    context = {
        **payload,
        "discover_domain": domain,
        "discover_query": query,
        "current_type": requested_type if requested_type in DISCOVER_TYPES else "",
        "domain_supported": domain_supported,
        "is_recent": not query and not requested_type,
    }
    return render(request, "discover/placeholder.html", context)


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
