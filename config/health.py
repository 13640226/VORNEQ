import os
import re
import time

import structlog
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import connection
from django.http import JsonResponse


logger = structlog.get_logger(__name__)


_SHA_CHARS = frozenset("0123456789abcdef")

# Render Postgres host names: internal "dpg-<id>-a", external
# "dpg-<id>-a.<region>-postgres.render.com". Only the instance id is reported.
_RENDER_DB_HOST_RE = re.compile(r"^(dpg-[a-z0-9]{8,40}-[a-z])(?:\.[a-z0-9.-]+)?$")
_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,63}$")


def release_identifier():
    """Return the deployed commit for external deploy verification.

    Render sets RENDER_GIT_COMMIT for every build. VORNEQ_RELEASE remains an
    explicit override. Anything that is not a plausible lower-case hex commit
    id is reported as "unknown" so arbitrary environment content is never
    echoed by this public endpoint.
    """
    for name in ("VORNEQ_RELEASE", "RENDER_GIT_COMMIT"):
        value = (os.environ.get(name) or "").strip().lower()
        if 7 <= len(value) <= 40 and set(value) <= _SHA_CHARS:
            return value
    return "unknown"


def render_database_id(host):
    """Return the Render Postgres instance id from a host name, else "other".

    Credentials, ports and IP addresses are never part of the result.
    """
    host = (host or "").strip().lower()
    if not host:
        return "unknown"
    match = _RENDER_DB_HOST_RE.match(host)
    return match.group(1) if match else "other"


def database_identity():
    """Identity of the database this process is connected to (G5 / C02).

    Reports the database name as seen by the server (current_database()) and
    the Render instance id derived from the configured host. No user name,
    password, IP address, port or connection string is included. Any failure
    yields "unknown" values instead of an exception.
    """
    identity = {"vendor": connection.vendor, "name": "unknown", "render_id": "unknown"}
    if connection.vendor != "postgresql":
        return identity
    identity["render_id"] = render_database_id(connection.settings_dict.get("HOST"))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            name = cursor.fetchone()[0]
    except Exception:
        logger.exception("health.database_identity_failed")
        return identity
    identity["name"] = name if isinstance(name, str) and _DB_NAME_RE.match(name) else "unknown"
    return identity


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
        "release": release_identifier(),
        "database": database_identity() if checks["database"] == "ok" else {
            "vendor": connection.vendor, "name": "unknown", "render_id": "unknown",
        },
    }

    logger.info(
        "health.completed",
        status=payload["status"],
        duration_ms=duration_ms,
    )
    response = JsonResponse(payload, status=200 if healthy else 503)
    if request.method == "HEAD":
        response.content = b""
    return response
