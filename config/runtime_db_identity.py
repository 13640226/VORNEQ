"""Temporary, fail-closed runtime database identity probe."""

import os
import secrets

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def runtime_db_identity(request):
    enabled_raw = os.environ.get("VORNEQ_RUNTIME_DB_IDENTITY_ENABLED", "")
    enabled = enabled_raw.strip().lower()
    expected_token = os.environ.get("VORNEQ_RUNTIME_DB_IDENTITY_TOKEN", "")
    provided_token = request.headers.get("X-VORNEQ-Runtime-DB-Identity-Token", "")

    if enabled not in {"1", "true", "yes", "on"}:
        response = JsonResponse({"detail": "Not found."}, status=404)
        response["Cache-Control"] = "no-store"
        return response

    token_match = (
        bool(expected_token)
        and bool(provided_token)
        and secrets.compare_digest(provided_token, expected_token)
    )

    if not token_match:
        response = JsonResponse(
            {
                "diagnostic": {
                    "enabled_configured": bool(enabled_raw),
                    "enabled_recognized": True,
                    "token_configured": bool(expected_token),
                    "token_header_present": bool(provided_token),
                    "token_match": False,
                    "request_headers_present": (
                        "X-VORNEQ-Runtime-DB-Identity-Token" in request.headers
                    ),
                    "wsgi_http_header_present": (
                        "HTTP_X_VORNEQ_RUNTIME_DB_IDENTITY_TOKEN" in request.META
                    ),
                    "wsgi_raw_header_variant_present": (
                        "X-VORNEQ-Runtime-DB-Identity-Token" in request.META
                    ),
                    "authorization_header_present": (
                        "HTTP_AUTHORIZATION" in request.META
                    ),
                }
            },
            status=403,
        )
        response["Cache-Control"] = "no-store"
        return response

    sql = """
    SELECT
        current_database(),
        inet_server_addr()::text,
        inet_server_port(),
        current_setting('server_version')
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)
        database_name, server_address, server_port, server_version = cursor.fetchone()

    response = JsonResponse(
        {
            "database_name": database_name,
            "server_address": server_address,
            "server_port": server_port,
            "server_version": server_version,
        }
    )
    response["Cache-Control"] = "no-store"
    return response
