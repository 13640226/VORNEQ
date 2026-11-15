#!/usr/bin/env python3
"""Reconcile an operator-captured read-only Django snapshot with LIVE Render API.

LOCAL/CI utility, not a Production Django migration command.
No secrets in output. No HTTP write methods. Does not prove TLS backend identity.
Example:
  RENDER_API_KEY=<secret> python scripts/c02_tests/verify_render_control_plane.py \
      --snapshot c02-runtime.json --expected-sha <sha>

The snapshot must come from the Render Production shell c02_runtime_observation
command. This tool independently fetches control-plane metadata using an
authenticated Render API token, never from the app's DATABASE_URL.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from django.core.management.base import CommandError
from apps.core.c02_resource_attestation import (
    EXPECTED_POSTGRES_ID, EXPECTED_SERVICE_ID, reconcile_render_metadata,
)

API_BASE = "https://api.render.com/v1"


def _fetch_json(endpoint, token):
    if not token:
        raise ValueError("RENDER_API_KEY must be provided securely in local environment")
    request = urllib.request.Request(
        API_BASE + endpoint,
        method="GET",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "User-Agent": "vorneq-c02-readonly-resource-verify",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError("Unexpected Render API response status")
        return json.loads(response.read(500000).decode("utf-8"))


def _unwrap(document, key):
    if not isinstance(document, dict):
        raise ValueError("Render API returned invalid metadata")
    value = document.get(key, document)
    if not isinstance(value, dict):
        raise ValueError("Render API returned invalid object")
    return value


def run(snapshot, expected_sha, token):
    db = _unwrap(_fetch_json("/postgres/" + EXPECTED_POSTGRES_ID, token), "postgres")
    service = _unwrap(_fetch_json("/services/" + EXPECTED_SERVICE_ID, token), "service")
    return reconcile_render_metadata(db, service, snapshot, expected_sha)


def main():
    parser = argparse.ArgumentParser(description="C02 authenticated Render API read-only metadata check")
    parser.add_argument("--snapshot", required=True, help="Read-only Django runtime JSON file")
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        with open(args.snapshot, encoding="utf-8") as file:
            snapshot = json.load(file)
        result = run(snapshot, args.expected_sha, os.environ.get("RENDER_API_KEY", ""))
    except (OSError, ValueError, KeyError, CommandError, urllib.error.URLError) as exc:
        # No token, HTTP response body, connection URL or private data in output.
        print("C02_CONTROL_PLANE_CROSS_SOURCE_CHECK: FAIL_CLOSED (" + type(exc).__name__ + ")")
        return 2
    print(json.dumps(result, sort_keys=True))
    print("C02_AUTHENTICATED_RENDER_API_METADATA: MATCH")
    print("C02_INDEPENDENT_POSTGRES_BACKEND_ATTESTATION: NOT_ESTABLISHED")
    print("C02_MIGRATION_GO: NO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
