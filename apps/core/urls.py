from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("reputation/<int:user_id>/", views.reputation_detail, name="reputation-detail"),
]
