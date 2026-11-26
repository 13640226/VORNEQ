import os
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.test import RequestFactory, override_settings
from django.contrib.auth import get_user_model
from apps.ai_core.image_generation.page import image_studio_page
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from django.urls import reverse
import json
root=Path(os.environ["TEMP"])/"ui03-fixtures"
root.mkdir(exist_ok=True)
user=get_user_model()(pk=3, username="synthetic-ui03", is_staff=True, is_superuser=True)
for lang in ("en","de","fa"):
    for preview in (False,True):
        request=RequestFactory().get(reverse("ai_core:image-studio"),{"lang":lang})
        request.user=user
        with override_settings(VORNEQ_ENV="staging",DEBUG=False,VORNEQ_AI_IMAGE_UI_ENABLED=True), patch("apps.ai_core.image_generation.page.production_studio_preview_allowed",return_value=preview), patch("apps.ai_core.image_generation.page.image_studio_allowed",return_value=not preview), patch("config.views._ai_chat_available_for",return_value=False):
            response=image_studio_page(request)
        assert response.status_code==200
        (root/(lang+("-preview" if preview else "")+".html")).write_bytes(response.content)
print("FIXTURES:",root)
print("STATIC_ROOT:",settings.STATIC_ROOT)
print("STATIC_URL:",settings.STATIC_URL)
print("CSP:",getattr(settings,"CONTENT_SECURITY_POLICY",{}))
