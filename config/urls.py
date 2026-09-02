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
    # --------------------------------------------------------
    # Language switching
    # --------------------------------------------------------
    path(
        "i18n/",
        include("django.conf.urls.i18n"),
    ),
]


# ============================================================
# LANGUAGE-AWARE URLS
# ============================================================

urlpatterns += i18n_patterns(

    # --------------------------------------------------------
    # Django Admin
    # --------------------------------------------------------
    path(
        "admin/",
        admin.site.urls,
    ),

    # --------------------------------------------------------
    # Home
    # --------------------------------------------------------
    path(
        "",
        home,
        name="home",
    ),

    # --------------------------------------------------------
    # Authentication — django-allauth
    # --------------------------------------------------------
    path(
        "accounts/",
        include("allauth.urls"),
    ),

    # --------------------------------------------------------
    # Library
    # --------------------------------------------------------
    path(
        "library/",
        include("library.urls"),
    ),

    # --------------------------------------------------------
    # Marketplace
    # --------------------------------------------------------
    path(
        "marketplace/",
        include("marketplace.urls"),
    ),

    # زبان پیش‌فرض هم prefix داشته باشد:
    # /fa/
    # /en/
    # /de/
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