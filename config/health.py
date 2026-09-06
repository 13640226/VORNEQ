import logging

from django.core.files.storage import default_storage
from django.db import connection
from django.http import JsonResponse


logger = logging.getLogger(__name__)


def health_check(request):
    """Read-only liveness/readiness check for database and default storage."""
    checks = {
        "database": "ok",
        "storage": "ok",
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Database health check failed")
        checks["database"] = "error"

    try:
        # ``exists`` is intentionally read-only. The sentinel is not expected
        # to exist; the call is used to verify that the storage backend can be
        # reached/configured without creating or deleting objects.
        default_storage.exists("__vorneq_healthcheck__")
    except Exception:
        logger.exception("Storage health check failed")
        checks["storage"] = "error"

    healthy = all(value == "ok" for value in checks.values())
    payload = {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
    }
    return JsonResponse(payload, status=200 if healthy else 503)
