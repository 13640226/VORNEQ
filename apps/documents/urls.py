from django.urls import path

from . import views


app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="list"),
    path("create/", views.document_create, name="create"),
    path("<int:document_id>/", views.document_detail, name="detail"),
    path("<int:document_id>/update/", views.document_update, name="update"),
    path("<int:document_id>/share/", views.document_share, name="share"),
    path("<int:document_id>/revoke/", views.document_revoke, name="revoke"),
]
