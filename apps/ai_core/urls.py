from django.urls import path

from .views import ask
from .views_phase_b import ask_phase_b
from .chat_page import chat_page
from .views_global import ask_global_view, recovery_status_view
from .views_conversations import (
    conversation_detail_view, conversation_export_view, conversation_message_view,
    conversation_restore_view, conversations_view,
)

app_name = "ai_core"
urlpatterns = [
    path("ask/", ask, name="ask"),
    path("ask-grounded/", ask_phase_b, name="ask-grounded"),
    path("chat/", chat_page, name="chat"),
    path("ask-global/", ask_global_view, name="ask-global"),
    path("request-status/", recovery_status_view, name="request-status"),
    path("conversations/", conversations_view, name="conversations"),
    path("conversations/<uuid:conversation_id>/", conversation_detail_view, name="conversation-detail"),
    path("conversations/<uuid:conversation_id>/messages/", conversation_message_view,
         name="conversation-messages"),
    path("conversations/<uuid:conversation_id>/restore/", conversation_restore_view,
         name="conversation-restore"),
    path("conversations/<uuid:conversation_id>/export/", conversation_export_view,
         name="conversation-export"),
]
