"""
URL configuration for VORNEQ.
"""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.platform_shell.registry import registry as platform_registry
from config.health import health_check
from config.inspect_views import context_view, inspect_entry
from config.metrics import metrics_view
from config.views import home, profile, search_page


# Non-localized operational and API endpoints.
urlpatterns = [
    path("health/", health_check, name="health"),
    path("metrics", metrics_view, name="prometheus-django-metrics"),
    path("", include("django_prometheus.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/", include("apps.core.urls")),
    path("api/verification/", include("apps.verification.urls")),
    path("api/media/", include("apps.media.urls")),
    path("api/search/", include("apps.search.urls")),
]


urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("search/", search_page, name="search_page"),
    path("inspect/", inspect_entry, name="inspect_entry"),
    path("context/<uuid:artifact_id>/", context_view, name="context_view"),
    path("profile/", profile, name="profile"),
    path("", include("apps.profiles.urls")),
    path("accounts/", include("allauth.urls")),
    path("apps/", include("apps.platform_shell.urls")),
    path(
        "library/",
        RedirectView.as_view(
            pattern_name="marketplace:index",
            permanent=True,
            query_string=True,
        ),
        name="legacy_library_index",
    ),
    # Keep legacy detail/reader routes alive until Marketplace has explicit
    # equivalents, so purchased content and historical links do not break.
    path("library/", include("library.urls")),
    path("graph/", include("apps.graph.urls")),
    *platform_registry.localized_urlpatterns(),
    prefix_default_language=True,
)


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
