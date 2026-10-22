#!/usr/bin/env python3
"""Read-only database identity probe and fail-closed target guard.

Used by GitHub Actions workflows that write to a database (seed, migrate,
DR restore) so they refuse to touch production unless the run explicitly
says so. Detection always comes from the database's real identity, never
from a flag: the flag can only *allow* a run that was already detected as
production.

Commands
  probe --env NAME [--compare-env NAME]
      Print a sanitized identity for the URL in env var NAME and, if given,
      whether it is the same database as --compare-env. Never prints
      user names, passwords or full connection strings.
  guard --target-env NAME [--production-env NAME]
      Exit non-zero unless the run is allowed. Reads CONFIRM and
      ALLOW_PRODUCTION_TARGET from the environment.

Standard library only; queries run through `psql` in a read-only session.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_PROTECTED_DATABASES = ("vorneq_production_db",)
PROTECTED_ENV = "VORNEQ_PROTECTED_DATABASES"

IDENTITY_SQL = (
    "SELECT current_database(), "
    "coalesce(inet_server_addr()::text, 'local'), "
    "coalesce(inet_server_port()::text, ''), "
    "current_setting('server_version_num')"
)


@dataclass(frozen=True)
class UrlInfo:
    host: str
    port: int
    database: str


@dataclass(frozen=True)
class Identity:
    database: str
    server_addr: str
    server_port: str
    server_version: str

    def same_database_as(self, other: "Identity") -> bool:
        return (self.database, self.server_addr, self.server_port) == (
            other.database,
            other.server_addr,
            other.server_port,
        )


def parse_url(url: str) -> UrlInfo:
    """Return only host, port and database name; credentials are dropped."""
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("not a PostgreSQL URL")
    host = (parsed.hostname or "").lower()
    database = parsed.path.lstrip("/")
    if not host or not database:
        raise ValueError("URL is missing host or database name")
    return UrlInfo(host=host, port=parsed.port or 5432, database=database)


def sanitized(url: str) -> str:
    info = parse_url(url)
    return f"host={info.host} port={info.port} database={info.database}"


def protected_databases(environ=os.environ) -> tuple[str, ...]:
    raw = environ.get(PROTECTED_ENV, "")
    names = tuple(n.strip() for n in raw.split(",") if n.strip())
    return names or DEFAULT_PROTECTED_DATABASES


def query_identity(url: str) -> Identity:
    env = dict(os.environ)
    # Every statement in this session is read-only, enforced by the server.
    env["PGOPTIONS"] = "-c default_transaction_read_only=on"
    result = subprocess.run(
        ["psql", url, "-X", "-A", "-t", "-F", "|", "-v", "ON_ERROR_STOP=1", "-c", IDENTITY_SQL],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    parts = result.stdout.strip().split("|")
    if len(parts) != 4:
        raise RuntimeError("unexpected identity response")
    return Identity(*parts)


def is_production(target: Identity, production: Identity | None, protected: tuple[str, ...]) -> bool:
    if production is not None and target.same_database_as(production):
        return True
    return target.database in protected


def decide(target_is_production: bool, allow_production: bool, confirmed: bool) -> tuple[bool, str]:
    """Pure decision rule; covered by the four-case matrix in the tests."""
    if not confirmed:
        return False, "REFUSING: run was not confirmed (confirm must be exactly 'yes')."
    if target_is_production and not allow_production:
        return False, (
            "REFUSING: target database is PRODUCTION. Re-run with "
            "allow_production_target=true only if production is the intended target."
        )
    if target_is_production:
        return True, "ALLOWED: explicit production target (allow_production_target=true)."
    return True, "ALLOWED: target is not production."


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "yes", "1"}


def _require_url(name: str) -> str:
    url = os.environ.get(name, "")
    if not url:
        raise SystemExit(f"{name} is empty or not configured.")
    return url


def cmd_probe(args: argparse.Namespace) -> int:
    url = _require_url(args.env)
    print(f"Secret under test: {args.env}")
    print(f"URL (sanitized):   {sanitized(url)}")
    identity = query_identity(url)
    print(f"current_database:  {identity.database}")
    print(f"server address:    {identity.server_addr}:{identity.server_port}")
    print(f"server_version:    {identity.server_version}")
    print(f"protected name:    {'yes' if identity.database in protected_databases() else 'no'}")
    if args.compare_env:
        other = query_identity(_require_url(args.compare_env))
        same = identity.same_database_as(other)
        print(f"same database as {args.compare_env}: {'YES' if same else 'no'}")
    return 0


def cmd_guard(args: argparse.Namespace) -> int:
    target_url = _require_url(args.target_env)
    target = query_identity(target_url)
    production = None
    if args.production_env and os.environ.get(args.production_env):
        production = query_identity(os.environ[args.production_env])
    target_is_prod = is_production(target, production, protected_databases())
    allow = _truthy(os.environ.get("ALLOW_PRODUCTION_TARGET"))
    confirmed = os.environ.get("CONFIRM", "") == "yes"

    print(f"Target secret: {args.target_env} -> {sanitized(target_url)}")
    print(f"Target identity: {target.database} @ {target.server_addr}:{target.server_port}")
    print(f"Detected as production: {'YES' if target_is_prod else 'no'}")
    ok, message = decide(target_is_prod, allow, confirmed)
    if ok and target_is_prod:
        # Prominent marker so production-targeted runs are easy to find in audits.
        print(f"::warning title=Production target::{message}")
    print(message)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("--env", required=True)
    probe.add_argument("--compare-env")
    probe.set_defaults(func=cmd_probe)
    guard = sub.add_parser("guard")
    guard.add_argument("--target-env", required=True)
    guard.add_argument("--production-env")
    guard.set_defaults(func=cmd_guard)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except subprocess.CalledProcessError:
        # psql's stderr may echo connection details; never forward it.
        print("REFUSING: could not read database identity (connection or query failed).", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"REFUSING: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
