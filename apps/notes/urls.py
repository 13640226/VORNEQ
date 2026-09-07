from django.urls import path

from . import views


app_name = "notes"

urlpatterns = [
    path("", views.note_list, name="list"),
    path("create/", views.note_create, name="create"),
    path("<int:note_id>/", views.note_detail, name="detail"),
    path("<int:note_id>/update/", views.note_update, name="update"),
    path("<int:note_id>/delete/", views.note_delete, name="delete"),
]
