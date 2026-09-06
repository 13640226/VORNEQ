"""
URL configuration for Saman Kherad.

سامان خرد — بنیاد عریان پرسش
"""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.views import home


# ============================================================
# URLS WITHOUT LANGUAGE PREFIX
# ============================================================

urlpatterns = [
    path(
        "i18n/",
        include("django.conf.urls.i18n"),
    ),
    path(
        "api/",
        include("apps.core.urls"),
    ),
    path(
        "api/verification/",
        include("apps.verification.urls"),
    ),
]


# ============================================================
# LANGUAGE-AWARE URLS
# ============================================================

urlpatterns += i18n_patterns(
    path(
        "admin/",
        admin.site.urls,
    ),
    path(
        "",
        home,
        name="home",
    ),
    path(
        "accounts/",
        include("allauth.urls"),
    ),
    path(
        "library/",
        include("library.urls"),
    ),
    path(
        "marketplace/",
        include("marketplace.urls"),
    ),
    path(
        "graph/",
        include("apps.graph.urls"),
    ),
    prefix_default_language=True,
)


# ============================================================
# MEDIA — DEVELOPMENT ONLY
# ============================================================

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
