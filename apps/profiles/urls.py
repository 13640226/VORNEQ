from django.urls import path

from .views import profile_avatar, profile_edit


urlpatterns = [
    path("profile/edit/", profile_edit, name="profile_edit"),
    path("profile/avatar/", profile_avatar, name="profile_avatar"),
]
