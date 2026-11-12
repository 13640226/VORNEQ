from django.urls import path
from .views import ask

app_name = "ai_core"
urlpatterns = [path("ask/", ask, name="ask")]
