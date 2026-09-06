"""
URL configuration for VORNEQ.
"""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from config.health import health_check
from config.views import home, profile


# Non-localized operational and API endpoints.
urlpatterns = [
    path("health/", health_check, name="health"),
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
    path("profile/", profile, name="profile"),
    path("", include("apps.profiles.urls")),
    path("accounts/", include("allauth.urls")),
    path(
        "library/",
        RedirectView.as_view(pattern_name="marketplace:index", permanent=True),
        name="legacy_library_index",
    ),
    # Keep legacy detail/reader routes alive until Marketplace has explicit
    # equivalents, so purchased content and historical links do not break.
    path("library/", include("library.urls")),
    path("marketplace/", include("marketplace.urls")),
    path("graph/", include("apps.graph.urls")),
    prefix_default_language=True,
)


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
