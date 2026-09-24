from django.urls import path

from apps.media.api import search_by_image, search_by_text


app_name = "media"

urlpatterns = [
    path("search/image/", search_by_image, name="search_image"),
    path("search/text/", search_by_text, name="search_text"),
]
