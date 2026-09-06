"""Render staging settings.

Keeps local development defaults in ``config.settings`` and overrides only
infrastructure concerns that are specific to Render/staging.
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


# Optional production object storage. Local development continues to use the
# FileSystemStorage configured in config.settings.
if env_bool("USE_OBJECT_STORAGE", False):  # noqa: F405
    bucket_name = os.environ.get("OBJECT_STORAGE_BUCKET")
    if not bucket_name:
        raise RuntimeError(
            "OBJECT_STORAGE_BUCKET is required when USE_OBJECT_STORAGE=True"
        )

    INSTALLED_APPS = [*INSTALLED_APPS, "storages"]  # noqa: F405

    storage_options = {
        "bucket_name": bucket_name,
        "default_acl": "private",
        "querystring_auth": True,
        "file_overwrite": False,
    }

    endpoint_url = os.environ.get("OBJECT_STORAGE_ENDPOINT_URL")
    if endpoint_url:
        storage_options["endpoint_url"] = endpoint_url

    region_name = os.environ.get("OBJECT_STORAGE_REGION")
    if region_name:
        storage_options["region_name"] = region_name

    access_key = os.environ.get("OBJECT_STORAGE_ACCESS_KEY_ID")
    if access_key:
        storage_options["access_key"] = access_key

    secret_key = os.environ.get("OBJECT_STORAGE_SECRET_ACCESS_KEY")
    if secret_key:
        storage_options["secret_key"] = secret_key

    STORAGES = {  # noqa: F405
        **STORAGES,  # noqa: F405
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": storage_options,
        },
    }
