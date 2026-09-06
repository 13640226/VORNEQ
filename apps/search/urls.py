from django.urls import path

from apps.search.views import unified_search


app_name = "search"

urlpatterns = [
    path("", unified_search, name="unified"),
]
