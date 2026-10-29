"""Canonical and alternate links on the seven public directory pages."""
from django.urls import reverse
from django.utils import translation

PUBLIC_SEO_ROUTES = frozenset({
    "discover", "discover_knowledge", "discover_media",
    "discover_software_services", "discover_products_commerce",
    "search_page", "marketplace:index",
})
SEO_LANGUAGES = ("fa", "en", "de")


def public_seo_context(request):
    """Account, private and dynamic detail views keep their indexing policy."""
    match = getattr(request, "resolver_match", None)
    if match is None or match.view_name not in PUBLIC_SEO_ROUTES:
        return {}
    language = getattr(request, "LANGUAGE_CODE", None) or translation.get_language()
    if language not in SEO_LANGUAGES:
        return {}
    alternates = []
    for code in SEO_LANGUAGES:
        with translation.override(code):
            path = reverse(match.view_name)
        alternates.append({"lang": code, "href": request.build_absolute_uri(path)})
    # Resolving the named route removes query strings; no host is hard-coded.
    return {"public_seo": {
        "canonical": next(link["href"] for link in alternates if link["lang"] == language),
        "alternates": alternates,
    }}
