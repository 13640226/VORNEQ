"""
URL configuration for the Marketplace app of Saman Kherad.

سامان خرد — بازار دیجیتال

Routes:
- /marketplace/
- /marketplace/seller/
- /marketplace/seller/create/
- /marketplace/seller/<pk>/edit/
- /marketplace/review/
- /marketplace/review/<pk>/
- /marketplace/<slug>/
"""

from django.urls import path

from . import views


app_name = "marketplace"


urlpatterns = [

    # ============================================================
    # PUBLIC MARKETPLACE
    # ============================================================

    path(
        "",
        views.index,
        name="index",
    ),


    # ============================================================
    # SELLER DASHBOARD
    # ============================================================

    path(
        "seller/",
        views.seller_dashboard,
        name="seller_dashboard",
    ),


    # ============================================================
    # CREATE PRODUCT
    # ============================================================

    path(
        "seller/create/",
        views.product_create,
        name="product_create",
    ),


    # ============================================================
    # EDIT PRODUCT
    # ============================================================

    path(
        "seller/<int:pk>/edit/",
        views.product_edit,
        name="product_edit",
    ),


    # ============================================================
    # MODERATION QUEUE
    # ============================================================

    path(
        "review/",
        views.review_queue,
        name="review_queue",
    ),


    # ============================================================
    # REVIEW ONE PRODUCT
    # ============================================================

    path(
        "review/<int:pk>/",
        views.review_product,
        name="review_product",
    ),


    # ============================================================
    # PRODUCT DETAIL
    #
    # Keep this route LAST.
    # Otherwise fixed routes such as seller/ and review/
    # could be interpreted as product slugs.
    # ============================================================

    path(
        "<slug:slug>/",
        views.detail,
        name="detail",
    ),

]