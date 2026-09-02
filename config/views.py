"""
Main views for Saman Kherad.

سامان خرد — بنیاد عریان پرسش
"""

from django.core.cache import cache
from django.shortcuts import render
from django.utils.translation import get_language

from library.models import AudioItem, LibraryItem
from marketplace.models import Product


# ============================================================
# HOME PAGE
# ============================================================

def home(request):
    """
    Render the Saman Kherad homepage.

    The homepage contains:
    - Latest published library items
    - Latest published audio items
    - Latest approved and published marketplace products

    Homepage data is cached separately for each language.
    """

    # --------------------------------------------------------
    # Current language
    # --------------------------------------------------------

    language = get_language() or "fa"

    cache_key = f"saman_kherad_homepage_{language}"


    # --------------------------------------------------------
    # Try cache first
    # --------------------------------------------------------

    context = cache.get(cache_key)


    # --------------------------------------------------------
    # Build homepage data
    # --------------------------------------------------------

    if context is None:

        # Latest library items
        library_items = list(
            LibraryItem.objects.filter(
                is_published=True,
            )
            .order_by("-created_at")[:6]
        )


        # Latest audio items that actually have a file
        audio_items = list(
            AudioItem.objects.filter(
                is_published=True,
            )
            .exclude(
                audio_file="",
            )
            .order_by("-created_at")[:4]
        )


        # Approved + published marketplace products
        approved_products = list(
            Product.objects.filter(
                status="approved",
                is_published=True,
            )
            .order_by("-created_at")[:6]
        )


        context = {
            "library_items": library_items,
            "audio_items": audio_items,
            "approved_products": approved_products,
        }


        # Cache for 5 minutes
        cache.set(
            cache_key,
            context,
            timeout=300,
        )


    # --------------------------------------------------------
    # Render
    # --------------------------------------------------------

    return render(
        request,
        "index.html",
        context,
    )