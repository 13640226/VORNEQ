"""
URL configuration for the Marketplace app of Saman Kherad.

سامان خرد — بازار دیجیتال
"""

from django.urls import path

from . import delivery, views


app_name = "marketplace"


urlpatterns = [
    path("", views.index, name="index"),
    path("seller/", views.seller_dashboard, name="seller_dashboard"),
    path("seller/create/", views.product_create, name="product_create"),
    path("seller/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("review/", views.review_queue, name="review_queue"),
    path("review/<int:pk>/", views.review_product, name="review_product"),
    path(
        "download/<int:product_id>/",
        delivery.download_product,
        name="download_product",
    ),
    # Keep the slug route last so fixed routes are not consumed as slugs.
    path("<slug:slug>/", views.detail, name="detail"),
]
