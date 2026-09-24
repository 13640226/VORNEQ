from django.urls import path

from . import views


app_name = "platform_shell"

urlpatterns = [
    path("home/", views.personal_home, name="personal_home"),
    path("", views.app_launcher, name="app_launcher"),
    path("workspace/", views.workspace_index, name="workspace_index"),
    path("workspace/<slug:slug>/", views.workspace_app, name="workspace_app"),
]
