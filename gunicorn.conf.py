"""Environment-scoped Gunicorn worker timeout for VORNEQ.

Gunicorn automatically discovers ./gunicorn.conf.py from the working directory
when started as `gunicorn config.wsgi:application` on Render.

Staging has a 60-second OpenAI request timeout, plus bounded retrieval and
persistence overhead. Production retains Gunicorn's prior 30-second default.
Do not enable automatic retries: provider retries remain max_retries=0.
"""
import os

timeout = 100 if os.environ.get("VORNEQ_ENV") == "staging" else 30
