from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.search.services import UnifiedSearch


ALLOWED_TYPES = {"article", "product", "libraryitem", "mediaasset", "audio"}
ALLOWED_LIBRARY_TYPES = {"book", "article", "document", "other"}
ALLOWED_MEDIA_TYPES = {"image", "video"}


def _positive_int(value, default, *, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    parsed = max(1, parsed)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _decimal_filter(value):
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


@require_GET
def unified_search(request):
    query = request.GET.get("q", "")
    requested_type = request.GET.get("type", "").strip().lower()
    item_type = request.GET.get("item_type", "").strip().lower()
    media_type = request.GET.get("media_type", "").strip().lower()

    filters = {}
    if requested_type in ALLOWED_TYPES:
        filters["types"] = {requested_type}
    if item_type in ALLOWED_LIBRARY_TYPES:
        filters["item_type"] = item_type
    if media_type in ALLOWED_MEDIA_TYPES:
        filters["media_type"] = media_type

    category = request.GET.get("category", "").strip()[:120]
    if category:
        filters["category"] = category

    price_min = _decimal_filter(request.GET.get("price_min"))
    price_max = _decimal_filter(request.GET.get("price_max"))
    if price_min is not None:
        filters["price_min"] = price_min
    if price_max is not None:
        filters["price_max"] = price_max

    page = _positive_int(request.GET.get("page"), 1)
    page_size = _positive_int(
        request.GET.get("page_size"),
        UnifiedSearch.DEFAULT_PAGE_SIZE,
        maximum=UnifiedSearch.MAX_PAGE_SIZE,
    )

    service = UnifiedSearch()
    normalized_query = service.normalize_query(query)
    payload = service.search(
        normalized_query,
        filters=filters,
        page=page,
        page_size=page_size,
        language=getattr(request, "LANGUAGE_CODE", None),
    )
    return JsonResponse(
        {
            "query": query.strip()[:200],
            "normalized_query": normalized_query,
            **payload,
        }
    )
