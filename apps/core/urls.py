from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("reputation/<int:user_id>/", views.reputation_detail, name="reputation-detail"),
    path(
        "reputation/user/<int:user_id>/",
        views.public_reputation_list,
        name="public-reputation-list",
    ),
    path(
        "reputation/user/<int:user_id>/<slug:domain>/<slug:method_code>/",
        views.public_reputation_context,
        name="public-reputation-context",
    ),
]
