"""Environment-scoped Gunicorn worker timeout for VORNEQ.

Gunicorn automatically discovers ./gunicorn.conf.py from the working directory
when started as `gunicorn config.wsgi:application` on Render.

Staging and Production have a 60-second OpenAI request timeout and 100-second
worker timeout, leaving headroom for retrieval, ledger settlement and recovery.
Development keeps the prior 30-second worker default.
Do not enable automatic retries: provider retries remain max_retries=0.
"""
import os

timeout = 100 if os.environ.get("VORNEQ_ENV") in ("staging", "production") else 30
