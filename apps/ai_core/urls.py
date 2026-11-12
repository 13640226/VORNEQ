from django.urls import path

from .views import ask
from .views_phase_b import ask_phase_b
from .chat_page import chat_page

app_name = "ai_core"
urlpatterns = [
    path("ask/", ask, name="ask"),
    path("ask-grounded/", ask_phase_b, name="ask-grounded"),
    path("chat/", chat_page, name="chat"),
]
