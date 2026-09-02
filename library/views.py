"""
Library views for Saman Kherad.

سامان خرد — آرشیو عریان

Includes:
- Library listing
- Search and filtering
- Pagination
- Multilingual document rendering
- Protected in-browser PDF reader
"""

from pathlib import Path

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import get_language

from .models import LibraryItem


# ============================================================
# HELPERS
# ============================================================

def _login_redirect(request):
    """
    Redirect an anonymous user to the login page while preserving
    the current destination.
    """

    return redirect(
        f"{settings.LOGIN_URL}?next={request.get_full_path()}"
    )


def _can_read(request, item):
    """
    Determine whether the current user may read this item.
    """

    if item.allow_public_reading:
        return True

    return request.user.is_authenticated


# ============================================================
# LIBRARY INDEX
# ============================================================

def index(request):
    """
    Display published library items.

    Supports:
    - multilingual search
    - content-type filtering
    - pagination
    """

    language = get_language() or "fa"

    query = request.GET.get(
        "q",
        "",
    ).strip()

    item_type = request.GET.get(
        "type",
        "",
    ).strip()


    # --------------------------------------------------------
    # Base queryset
    # --------------------------------------------------------

    items = LibraryItem.objects.filter(
        is_published=True,
    )


    # --------------------------------------------------------
    # Content-type filter
    # --------------------------------------------------------

    valid_types = {
        value
        for value, label in LibraryItem.TYPE_CHOICES
    }

    if item_type in valid_types:
        items = items.filter(
            item_type=item_type,
        )


    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    if query:

        items = items.filter(

            Q(
                title__icontains=query,
            )

            | Q(
                title_en__icontains=query,
            )

            | Q(
                title_de__icontains=query,
            )

            | Q(
                author__icontains=query,
            )

            | Q(
                category__icontains=query,
            )

            | Q(
                short_description__icontains=query,
            )

            | Q(
                short_description_en__icontains=query,
            )

            | Q(
                short_description_de__icontains=query,
            )

            | Q(
                content__icontains=query,
            )

            | Q(
                content_en__icontains=query,
            )

            | Q(
                content_de__icontains=query,
            )
        )


    # --------------------------------------------------------
    # Ordering
    # --------------------------------------------------------

    items = items.order_by(
        "-published_at",
        "-created_at",
    )


    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    paginator = Paginator(
        items,
        10,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )


    # --------------------------------------------------------
    # Context
    # --------------------------------------------------------

    context = {
        "items": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,

        "query": query,
        "selected_type": item_type,

        "item_types": LibraryItem.TYPE_CHOICES,

        "language": language,
    }


    return render(
        request,
        "library/index.html",
        context,
    )


# ============================================================
# LIBRARY DETAIL
# ============================================================

def detail(request, slug):
    """
    Display one published library document.

    If public reading is disabled, authentication is required.
    """

    language = get_language() or "fa"


    item = get_object_or_404(
        LibraryItem,
        slug=slug,
        is_published=True,
    )


    # --------------------------------------------------------
    # Access control
    # --------------------------------------------------------

    if not _can_read(
        request,
        item,
    ):
        return _login_redirect(request)


    # --------------------------------------------------------
    # Multilingual content
    # --------------------------------------------------------

    title = item.get_title(
        language,
    )

    short_description = item.get_short_description(
        language,
    )

    content = item.get_content(
        language,
    )


    # --------------------------------------------------------
    # Context
    # --------------------------------------------------------

    context = {
        "item": item,

        "title": title,
        "short_description": short_description,
        "content": content,

        "language": language,

        # Template only receives a boolean.
        # It does NOT receive pdf_file.url.
        "has_pdf": item.has_pdf,
    }


    return render(
        request,
        "library/detail.html",
        context,
    )


# ============================================================
# PROTECTED PDF READER
# ============================================================

def serve_pdf(request, slug):
    """
    Serve a published PDF for in-browser reading.

    Important:
    - No direct pdf_file.url is exposed by this view.
    - Content-Disposition is inline.
    - Private documents require authentication.
    - The response may be embedded by pages on the same origin.

    This discourages direct downloading but is not DRM.
    """

    item = get_object_or_404(
        LibraryItem,
        slug=slug,
        is_published=True,
    )


    # --------------------------------------------------------
    # Access control
    # --------------------------------------------------------

    if not _can_read(
        request,
        item,
    ):
        return _login_redirect(request)


    # --------------------------------------------------------
    # File existence
    # --------------------------------------------------------

    if not item.pdf_file:
        raise Http404(
            _("PDF file not found.")
        )


    try:
        pdf_path = Path(
            item.pdf_file.path
        )
    except (NotImplementedError, ValueError):
        raise Http404(
            _("PDF file not found.")
        )


    if (
        not pdf_path.exists()
        or not pdf_path.is_file()
    ):
        raise Http404(
            _("PDF file not found.")
        )


    # --------------------------------------------------------
    # Validate extension
    # --------------------------------------------------------

    if pdf_path.suffix.lower() != ".pdf":
        raise Http404(
            _("Invalid PDF file.")
        )


    # --------------------------------------------------------
    # Open protected file
    # --------------------------------------------------------

    try:
        pdf_stream = pdf_path.open(
            "rb"
        )
    except OSError:
        raise Http404(
            _("PDF file could not be opened.")
        )


    response = FileResponse(
        pdf_stream,
        content_type="application/pdf",
    )


    # --------------------------------------------------------
    # Inline display
    # --------------------------------------------------------

    # We deliberately do not expose the physical filename.
    response["Content-Disposition"] = (
        'inline; filename="reader.pdf"'
    )


    # --------------------------------------------------------
    # Same-origin embedding
    # --------------------------------------------------------

    response["X-Frame-Options"] = (
        "SAMEORIGIN"
    )


    # --------------------------------------------------------
    # MIME protection
    # --------------------------------------------------------

    response["X-Content-Type-Options"] = (
        "nosniff"
    )


    # --------------------------------------------------------
    # Referrer protection
    # --------------------------------------------------------

    response["Referrer-Policy"] = (
        "same-origin"
    )


    # --------------------------------------------------------
    # Avoid persistent caching
    # --------------------------------------------------------

    response["Cache-Control"] = (
        "private, no-store, max-age=0"
    )

    response["Pragma"] = (
        "no-cache"
    )

    response["Expires"] = (
        "0"
    )


    return response