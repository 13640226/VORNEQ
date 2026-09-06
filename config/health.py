import os
import time

import structlog
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import connection
from django.http import JsonResponse


logger = structlog.get_logger(__name__)


def health_check(request):
    """Read-only readiness check for database, storage, and cache."""
    started = time.monotonic()
    checks = {
        "database": "ok",
        "storage": "ok",
        "cache": "ok",
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("health.database_failed")
        checks["database"] = "error"

    try:
        default_storage.exists("__vorneq_healthcheck__")
    except Exception:
        logger.exception("health.storage_failed")
        checks["storage"] = "error"

    try:
        cache.get("__vorneq_healthcheck__")
    except Exception:
        logger.exception("health.cache_failed")
        checks["cache"] = "error"

    healthy = all(value == "ok" for value in checks.values())
    duration_ms = round((time.monotonic() - started) * 1000, 2)
    payload = {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        "duration_ms": duration_ms,
        "release": os.environ.get("VORNEQ_RELEASE", "unknown"),
    }

    logger.info(
        "health.completed",
        status=payload["status"],
        duration_ms=duration_ms,
    )
    return JsonResponse(payload, status=200 if healthy else 503)
