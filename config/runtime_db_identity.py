"""Temporary, fail-closed runtime database identity probe."""

import os
import secrets

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def runtime_db_identity(request):
    enabled = os.environ.get("VORNEQ_RUNTIME_DB_IDENTITY_ENABLED", "").strip().lower()
    expected_token = os.environ.get("VORNEQ_RUNTIME_DB_IDENTITY_TOKEN", "")

    if enabled not in {"1", "true", "yes", "on"} or not expected_token:
        response = JsonResponse({"detail": "Not found."}, status=404)
        response["Cache-Control"] = "no-store"
        return response

    provided_token = request.headers.get("X-VORNEQ-Runtime-DB-Identity-Token", "")
    if not provided_token or not secrets.compare_digest(provided_token, expected_token):
        response = JsonResponse({"detail": "Not found."}, status=404)
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
