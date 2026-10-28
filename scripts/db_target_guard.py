#!/usr/bin/env python3
"""C02 V1.1: diagnostic database identity probe; fail-closed operation guard.

SECURITY STATUS: REVIEW REQUIRED. No operation authorization is implemented.
This tool cannot establish independent target authority, prevent a subsequent
command from changing its connection, or prove a Render runtime binding.
Accordingly, 'guard' ALWAYS denies, including when a probe succeeds.
Do not treat 'probe' success as permission to migrate, seed, restore or delete.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit

# Names are only negative indicators. Absence from this list is NEVER proof
# that a database is non-production.
PROTECTED_NAMES = frozenset({"vorneq_production_db"})
IDENTITY_SQL = (
    "SELECT current_database(), "
    "coalesce(inet_server_addr()::text, 'local'), "
    "coalesce(inet_server_port()::text, ''), "
    "coalesce((SELECT system_identifier::text FROM pg_control_system()), '')"
)
SAFE_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Classification(str, Enum):
    PRODUCTION = "PRODUCTION"
    NON_PRODUCTION = "NON_PRODUCTION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Identity:
    database: str
    server_address: str
    server_port: str
    system_identifier: str


class IdentityError(Exception):
    """Expected probe failure. Never include secrets in the message."""


def get_url(name: str) -> str:
    if not SAFE_ENV_NAME.fullmatch(name):
        raise IdentityError("invalid environment variable name")
    value = os.environ.get(name)
    if not value:
        raise IdentityError("connection environment variable missing")
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError()
        if not parsed.hostname or not parsed.path.strip("/"):
            raise ValueError()
        _ = parsed.port
    except (ValueError, AttributeError):
        raise IdentityError("invalid PostgreSQL connection URL") from None
    return value


def query_identity(url: str, timeout: int = 8) -> Identity:
    # No URL on command line. Do not inherit libpq configuration or service
    # files from the caller. These measures reduce accidental disclosure,
    # but cannot guarantee secrecy against privileged process inspection.
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "PGDATABASE": url,
        "PGOPTIONS": "-c default_transaction_read_only=on "
                     "-c statement_timeout=5000 "
                     "-c lock_timeout=1000",
        "PGCONNECT_TIMEOUT": "5",
        "PGPASSFILE": "/dev/null",
        "PGSERVICEFILE": "/dev/null",
        "PGSYSCONFDIR": "/nonexistent",
        "PGAPPNAME": "vorneq-c02-diagnostic",
    }
    try:
        result = subprocess.run(
            ["/usr/bin/psql", "-X", "-q", "-A", "-t",
             "-F", "|", "-v", "ON_ERROR_STOP=1", "-c", IDENTITY_SQL],
            env=env, capture_output=True, text=True, timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise IdentityError("database identity probe unavailable") from None
    if result.returncode != 0:
        # Never surface stderr; libpq/psql can echo connection details.
        raise IdentityError("database identity query failed") from None
    lines = result.stdout.splitlines()
    if len(lines) != 1:
        raise IdentityError("unexpected identity response")
    parts = lines[0].split("|")
    if len(parts) != 4 or any(not p.strip() for p in parts):
        raise IdentityError("incomplete identity response")
    database, address, port, system_id = parts
    if not system_id.isdecimal() or not port.isdecimal():
        raise IdentityError("invalid server identity response")
    return Identity(database, address, port, system_id)


def classify(identity: Identity | None) -> Classification:
    """Conservative diagnostic only, never an authorization decision."""
    if identity is None:
        return Classification.UNKNOWN
    if identity.database in PROTECTED_NAMES:
        return Classification.PRODUCTION
    # A valid connection with an unprotected name is NOT independent
    # evidence of a permitted non-production destination.
    return Classification.UNKNOWN


def cmd_probe(args: argparse.Namespace) -> int:
    try:
        identity = query_identity(get_url(args.env))
        category = classify(identity)
        # Avoid printing host/IP, URL, user, passwords, system identifier.
        print(json.dumps({
            "classification": category.value,
            "database_name": identity.database,
            "identity_observed": True,
            "authorization": "DENY",
            "note": "diagnostic observation only; not target authorization",
        }, sort_keys=True))
        # Probe exit 0 means diagnostic succeeded, NEVER authorization.
        return 0
    except IdentityError:
        print(json.dumps({
            "classification": Classification.UNKNOWN.value,
            "identity_observed": False,
            "authorization": "DENY",
        }, sort_keys=True))
        return 2


def cmd_guard(args: argparse.Namespace) -> int:
    # Never query a DB in the authorization path until an independent
    # authority and same-target enforcement contract are implemented and
    # independently reviewed. Flags cannot override this hard stop.
    print(
        "DENY: C02 guard V1.1 has no verified independent identity "
        "authority or same-target execution binding.",
        file=sys.stderr,
    )
    return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe", help="diagnostic only; never authorizes")
    probe.add_argument("--env", required=True)
    probe.add_argument("--compare-env", help="legacy option; unsupported")
    probe.set_defaults(func=cmd_probe)
    guard = sub.add_parser("guard", help="fail-closed; always denies")
    guard.add_argument("--target-env", required=True)
    guard.add_argument("--production-env")
    guard.set_defaults(func=cmd_guard)
    args = parser.parse_args(argv)
    if args.command == "probe" and args.compare_env:
        print("DENY: compare-env unsupported in C02 V1.1", file=sys.stderr)
        return 3
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
