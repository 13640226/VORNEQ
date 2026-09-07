from django.urls import path

from . import views


app_name = "platform_shell"

urlpatterns = [
    path("", views.app_launcher, name="app_launcher"),
]
