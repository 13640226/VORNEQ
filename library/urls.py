"""
URL configuration for the Saman Kherad Library.

سامان خرد — آرشیو عریان

Routes:
- /library/
- /library/audio/<pk>/
- /library/<slug>/
- /library/<slug>/read/
"""

from django.urls import path

from . import views


# ============================================================
# APPLICATION NAMESPACE
# ============================================================

app_name = "library"


# ============================================================
# URL PATTERNS
# ============================================================

urlpatterns = [

    # --------------------------------------------------------
    # Library index
    # --------------------------------------------------------

    path(
        "",
        views.index,
        name="index",
    ),


    # --------------------------------------------------------
    # Audio detail
    # --------------------------------------------------------

    path(
        "audio/<int:pk>/",
        views.audio_detail,
        name="audio_detail",
    ),


    # --------------------------------------------------------
    # Protected PDF reader
    # --------------------------------------------------------

    path(
        "<slug:slug>/read/",
        views.serve_pdf,
        name="serve_pdf",
    ),


    # --------------------------------------------------------
    # Document detail
    # --------------------------------------------------------

    path(
        "<slug:slug>/",
        views.detail,
        name="detail",
    ),
]
