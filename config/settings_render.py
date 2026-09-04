"""Render staging settings.

Keeps the default settings unchanged for local development while configuring
Render's PostgreSQL database from DATABASE_URL.
"""

import os

import dj_database_url

from .settings import *  # noqa: F403,F401


DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,
    )
}

if not os.environ.get("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is required for Render staging")
