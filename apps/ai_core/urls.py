from django.urls import path

from .views import ask
from .voice.views import voice_event_view, voice_session_close_view, voice_session_create_view
from .views_phase_b import ask_phase_b
from .chat_page import chat_page
from .image_generation.gallery import image_download_view, image_history_view
from .image_generation.views import image_jobs_view, image_job_detail_view
from .image_generation.page import image_studio_page
from .views_global import ask_global_view, recovery_status_view
from .views_streaming import conversation_message_cancel_view, conversation_message_stream_view
from .views_conversations import (
    conversation_detail_view, conversation_export_view, conversation_message_view,
    conversation_restore_view, conversations_view,
)

app_name = "ai_core"
urlpatterns = [
    path("ask/", ask, name="ask"),
    path("ask-grounded/", ask_phase_b, name="ask-grounded"),
    path("chat/", chat_page, name="chat"),
    # Separate, default-off image generation capability.
    path("images/studio/", image_studio_page, name="image-studio"),
    path("images/jobs/", image_jobs_view, name="image-jobs"),
    path("images/jobs/history/", image_history_view, name="image-history"),
    path("images/jobs/<uuid:job_id>/", image_job_detail_view, name="image-job-detail"),
    path("images/jobs/<uuid:job_id>/download/", image_download_view, name="image-job-download"),
    # Separate, default-off, mock-only Voice foundation.
    path("voice/sessions/", voice_session_create_view, name="voice-session-create"),
    path("voice/sessions/<uuid:session_id>/events/", voice_event_view, name="voice-event"),
    path("voice/sessions/<uuid:session_id>/close/", voice_session_close_view, name="voice-session-close"),
    path("ask-global/", ask_global_view, name="ask-global"),
    path("request-status/", recovery_status_view, name="request-status"),
    path("conversations/", conversations_view, name="conversations"),
    path("conversations/<uuid:conversation_id>/", conversation_detail_view, name="conversation-detail"),
    path("conversations/<uuid:conversation_id>/messages/", conversation_message_view,
         name="conversation-messages"),
    # V7-03: gestreamte Antwort und Stop (eigene Gates, Standard aus).
    path("conversations/<uuid:conversation_id>/messages/stream/", conversation_message_stream_view,
         name="conversation-messages-stream"),
    path("conversations/<uuid:conversation_id>/messages/<uuid:message_id>/cancel/",
         conversation_message_cancel_view, name="conversation-message-cancel"),
    path("conversations/<uuid:conversation_id>/restore/", conversation_restore_view,
         name="conversation-restore"),
    path("conversations/<uuid:conversation_id>/export/", conversation_export_view,
         name="conversation-export"),
]
