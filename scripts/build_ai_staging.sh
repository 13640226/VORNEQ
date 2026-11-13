#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements-ai-staging.txt
python -c "import openai; from openai import OpenAI; print('G01_SDK_IMPORT_OK')"
python manage.py compilemessages
DJANGO_SETTINGS_MODULE=config.settings_render python manage.py collectstatic --noinput
