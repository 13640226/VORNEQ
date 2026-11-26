"""Main views for VORNEQ."""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import get_language

from apps.ai_core.chat_strings import chat_labels
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


def robots_txt(request):
    """Expose a minimal crawl policy for public surfaces."""
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    return HttpResponse(f"User-agent: *\\nAllow: /\\nSitemap: {sitemap_url}\\n", content_type="text/plain")


def sitemap_xml(request):
    """Expose localized homepage URLs without adding a sitemap dependency."""
    locations = [request.build_absolute_uri(f"/{language}/") for language in ("fa", "en", "de")]
    body = '<?xml version="1.0" encoding="UTF-8"?>\\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n' + "".join(
        f"  <url><loc>{location}</loc></url>\\n" for location in locations
    ) + "</urlset>\\n"
    return HttpResponse(body, content_type="application/xml")


def _ai_chat_available_for(user):
    """Mirror the AI chat page's own server-side gates; never weaker.

    Anonymous visitors never reach the policy checks (keeps the public homepage
    free of AI configuration lookups and database queries). The link is a
    navigation hint only: the chat page and its API re-check every gate.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    from apps.ai_core.chat_page import is_chat_enabled
    if not is_chat_enabled():
        return False
    environment = getattr(settings, "VORNEQ_ENV", "")
    if environment == "staging":
        from apps.ai_core.staging_policy import actor_allowed
        return actor_allowed(user)
    if environment == "production":
        from apps.ai_core.production_policy import production_actor_allowed
        return production_actor_allowed(user)
    return environment == "development"


def _image_studio_available_for(user):
    """Mirror the Image Studio page gates for a navigation hint; never weaker.

    Anonymous visitors never reach the policy checks. The studio page and its
    job API re-check every gate; this only decides whether a link is shown.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    from apps.ai_core.image_generation.page import image_studio_allowed, production_studio_preview_allowed
    return bool(production_studio_preview_allowed(user) or image_studio_allowed(user))


def _recent_work_for(user, limit=3):
    """Owner-scoped recent documents and notes for the signed-in workspace.

    Reuses the domain services, so the same readability and ownership rules as
    the list pages apply. A user without a resolvable identity gets empty lists.
    """
    if not getattr(user, "is_authenticated", False):
        return [], []
    from django.core.exceptions import PermissionDenied

    from apps.documents.services import DocumentService
    from apps.notes.services import NoteService
    try:
        documents = DocumentService.personal_home_recent_documents(user=user, limit=limit)
    except PermissionDenied:
        documents = []
    try:
        notes = list(NoteService.list_notes(user)[:limit])
    except PermissionDenied:
        notes = []
    return documents, notes


def home(request):
    """Product-first workspace (V6-02): Search composer, gated AI links, own recent work."""
    chat_enabled = _ai_chat_available_for(request.user)
    labels = chat_labels(get_language(), environment=settings.VORNEQ_ENV) if chat_enabled else {}
    recent_documents, recent_notes = _recent_work_for(request.user)
    return render(request, "index.html", {
        "phase_c_chat_enabled": chat_enabled,
        "phase_c_chat_link_label": labels.get("entry", ""),
        "phase_c_chat_warning": labels.get("warning", ""),
        "image_studio_enabled": _image_studio_available_for(request.user),
        "recent_documents": recent_documents,
        "recent_notes": recent_notes,
    })


def orientation(request):
    """Render the public evidence vocabulary orientation surface."""
    return render(request, "orientation.html")


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

DISCOVER_AFFORDANCE_AVAILABLE = "AVAILABLE"
DISCOVER_AFFORDANCE_UNAVAILABLE = "UNAVAILABLE"


def _discover_artifact_for_result(result):
    """Resolve the existing active Artifact for a supported Discover result."""
    key = result.get("key", "")
    prefix, separator, object_id = key.partition(":")
    target = DISCOVER_GRAPH_TARGETS.get(prefix)
    if not separator or not object_id or target is None:
        return None

    return (
        Artifact.objects.filter(
            binding__content_type__app_label=target[0],
            binding__content_type__model=target[1],
            binding__object_id=object_id,
            is_active=True,
        )
        .only("id")
        .first()
    )


def _discover_graph_for_artifact(artifact):
    """Return Public Graph V1 for an already eligible Artifact, or None."""
    if artifact is None:
        return None
    try:
        return get_public_graph(artifact.pk)
    except PublicGraphUnavailable:
        return None


def _attach_discover_graphs(payload):
    """Attach bounded inspection affordances without creating canonical records."""
    enriched = []
    for result in payload["results"]:
        item = dict(result)
        artifact = _discover_artifact_for_result(item)
        context_available = artifact is not None
        item["context_availability"] = (
            DISCOVER_AFFORDANCE_AVAILABLE
            if context_available
            else DISCOVER_AFFORDANCE_UNAVAILABLE
        )
        item["context_url"] = (
            reverse("context_view", kwargs={"artifact_id": artifact.pk})
            if context_available
            else None
        )
        item["public_graph"] = _discover_graph_for_artifact(artifact)
        item["graph_availability"] = (
            DISCOVER_AFFORDANCE_AVAILABLE
            if item["public_graph"] is not None
            else DISCOVER_AFFORDANCE_UNAVAILABLE
        )
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


def shell_preview_allowed(request):
    """UI-01: Vorschau des App-Shells nur lokal oder für Staff.

    In jeder gehosteten Umgebung (Staging und Produktion) ist die Seite für
    normale Nutzer nicht vorhanden (404), damit kein halbfertiger Rahmen
    öffentlich erreichbar ist.
    """
    if getattr(settings, "VORNEQ_ENV", None) == "development":
        return True
    user = getattr(request, "user", None)
    return bool(user is not None and user.is_authenticated and user.is_staff)


def shell_test_view(request):
    if not shell_preview_allowed(request):
        raise Http404
    response = render(request, "shell/_test_page.html")
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Cache-Control"] = "private, no-store"
    return response
