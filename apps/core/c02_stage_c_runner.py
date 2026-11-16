"""C02 Stage C: guarded runner for exactly ai_core.0001 and ai_core.0002.

PRODUCTION WRITE PATH: PROPOSED FOR CONDITIONAL ENABLEMENT IN THIS BRANCH.
A guarded Production invocation still requires exact deployed SHA, explicit
SHA-bound one-use owner authorization, backup evidence and live session checks.
Merging or deploying this module by itself does not authorize a migration.

The runner executes, in one PostgreSQL transaction on one backend session:

 1. SHA-bound authorization (target-specific, before any SQL)
 2. database identity recheck in the live session
 3. transaction-scoped locks (django_migrations NOWAIT + advisory xact lock)
 4. empty pre-state and exact two-step migration plan
 5. atomic migration execution with session/transaction continuity checks
 6. pre-commit verification (tables, index, constraints, history, empty plan,
    unchanged source SHA); any failure rolls the whole transaction back
 7. commit (or deliberate rollback in rehearsal mode)
 8. post-commit verification in a separate READ ONLY transaction

The ``lab`` target only accepts a disposable local test database. Django's
``post_migrate`` signal (content types, permissions) is deliberately not
emitted: the write scope is exactly the two migrations.
"""
from __future__ import annotations

import hmac
import json
import re
import uuid
from dataclasses import dataclass
from typing import Callable

from django.db import transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from apps.core import c02_operational_binding as binding

PRODUCTION_WRITE_ENABLED = False  # C02 open: separate authorization needed

EXPECTED_PLAN = (("ai_core", "0001_initial"), ("ai_core", "0002_aichatrequestguard"))
TARGET = EXPECTED_PLAN[-1]
EXPECTED_TABLES = frozenset({"ai_core_stagingaibudgetday", "ai_core_aichatrequestguard"})
EXPECTED_INDEXES = frozenset({"ai_chat_guard_created_idx"})
EXPECTED_CONSTRAINTS = frozenset({"ai_staging_budget_nonnegative", "ai_staging_requests_nonnegative"})
ADVISORY_LOCK_KEY = 62520261116

PRODUCTION_SERVICE_ID = "srv-dadn07eq1p3s73eccau0"
PRODUCTION_PG_MAJOR = 18
LAB_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "postgres", "vorneq-c02-db"})
LAB_DATABASE = re.compile(r"(test_[a-z0-9_]+|isolated_c02_test)\Z")

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
AUTHORIZATION = re.compile(r"OWNER-AUTH-C02-MIGRATION-(?P<id>[A-Z0-9-]{6,60}) @ (?P<sha>[0-9a-f]{40})\Z")
BACKUP_EVIDENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{5,120}\Z")
_FALSY = ("", "0", "false", "no", "off")


class RunnerRefused(Exception):
    """Refused before any SQL was executed."""


class RunnerAborted(Exception):
    """Aborted after SQL started; the migration transaction was rolled back."""


class _Rehearsal(Exception):
    pass


@dataclass(frozen=True)
class Target:
    name: str
    database: str
    user: str
    pg_major: int | None
    release_id: str | None = None


def _require(condition: bool, message: str, error=RunnerRefused):
    if not condition:
        raise error(message)


def authorize(target_name: str, environ, expected_sha: str, settings_dict: dict, source_sha: str) -> Target:
    """Return the permitted target or raise RunnerRefused. Executes no SQL."""
    _require(isinstance(expected_sha, str) and bool(SHA40.fullmatch(expected_sha)), "expected SHA malformed")
    _require(isinstance(source_sha, str) and hmac.compare_digest(source_sha, expected_sha), "source SHA mismatch")
    if target_name == "production":
        _require(PRODUCTION_WRITE_ENABLED, "C02 OPEN: production write path disabled (PRODUCTION_WRITE_ENABLED=False)")
        _require(environ.get("VORNEQ_ENV") == "production", "production environment required")
        _require(environ.get("RENDER_SERVICE_ID") == PRODUCTION_SERVICE_ID, "Render service mismatch")
        _require(environ.get("RENDER_GIT_COMMIT", "") == expected_sha, "deployed SHA mismatch")
        auth = AUTHORIZATION.fullmatch(environ.get("VORNEQ_C02_MIGRATION_AUTH", ""))
        _require(bool(auth) and auth.group("sha") == expected_sha, "SHA-bound owner authorization missing")
        _require(bool(BACKUP_EVIDENCE.fullmatch(environ.get("VORNEQ_C02_BACKUP_EVIDENCE", ""))),
                 "point-of-use backup evidence reference missing")
        _require(str(environ.get("VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED", "")).lower() in _FALSY,
                 "AI must stay disabled during migration")
        url = environ.get("DATABASE_URL", "")
        _require(bool(url), "DATABASE_URL missing")
        _require(binding.classify_host(binding.parse_url(url)["HOST"]) == "INTERNAL_EXACT",
                 "DATABASE_URL is not the Render internal hostname")
        _require(binding.settings_match_url(settings_dict, url), "Django settings do not derive from DATABASE_URL")
        _require(settings_dict.get("NAME") == binding.EXPECTED_DATABASE
                 and settings_dict.get("USER") == binding.EXPECTED_DATABASE_USER, "logical database mismatch")
        return Target("production", binding.EXPECTED_DATABASE, binding.EXPECTED_DATABASE_USER, PRODUCTION_PG_MAJOR, auth.group("id"))
    if target_name == "lab":
        _require(environ.get("VORNEQ_ENV") == "development", "lab requires VORNEQ_ENV=development")
        _require(environ.get("C02_STAGE_C_LAB") == "YES", "lab requires explicit C02_STAGE_C_LAB=YES")
        _require(not any(key.startswith("RENDER_") for key in environ), "Render environment detected")
        _require(settings_dict.get("ENGINE", "").endswith("postgresql"), "PostgreSQL required")
        _require(settings_dict.get("HOST", "") in LAB_HOSTS, "lab database host not in local allowlist")
        name = settings_dict.get("NAME", "")
        _require(bool(LAB_DATABASE.fullmatch(name or "")), "lab database must be a disposable test database")
        _require(name != binding.EXPECTED_DATABASE, "production database name refused")
        return Target("lab", name, settings_dict.get("USER", ""), None)
    raise RunnerRefused("unknown target")


def _snapshot(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_backend_pid(), current_database(), current_user, "
            "current_setting('server_version_num')::int / 10000, "
            "current_setting('transaction_read_only'), pg_is_in_recovery(), "
            "txid_current_if_assigned()"
        )
        return cursor.fetchone()


def _check_identity(snapshot, target: Target, error):
    _, database, user, major, read_only, replica, _ = snapshot
    _require(database == target.database and user == target.user, "live session identity mismatch", error)
    _require(target.pg_major is None or major == target.pg_major, "PostgreSQL major mismatch", error)
    _require(replica is False and read_only == "off", "writable primary session required", error)


def _state(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname = current_schema() AND tablename = ANY(%s)",
            [sorted(EXPECTED_TABLES)],
        )
        tables = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM django_migrations WHERE app = 'ai_core'")
        rows = cursor.fetchone()[0]
    return tables, rows


def _verify_schema(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() AND tablename LIKE 'ai\\_core\\_%%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND indexname = ANY(%s)",
                       [sorted(EXPECTED_INDEXES)])
        indexes = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname = ANY(%s) AND c.convalidated",
            [sorted(EXPECTED_TABLES)],
        )
        constraints = {row[0] for row in cursor.fetchall()}
        cursor.execute("SELECT name FROM django_migrations WHERE app = 'ai_core' ORDER BY name")
        history = tuple(row[0] for row in cursor.fetchall())
    _require(tables == EXPECTED_TABLES, "unexpected ai_core tables after migration", RunnerAborted)
    _require(EXPECTED_INDEXES <= indexes, "expected index missing", RunnerAborted)
    _require(EXPECTED_CONSTRAINTS <= constraints, "expected validated constraints missing", RunnerAborted)
    _require(history == tuple(name for _, name in EXPECTED_PLAN), "unexpected ai_core migration history", RunnerAborted)


def _exact_plan(connection):
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    _require(not executor.loader.detect_conflicts(), "conflicting migrations", RunnerAborted)
    plan = executor.migration_plan([TARGET])
    items = tuple((migration.app_label, migration.name) for migration, backwards in plan)
    _require(items == EXPECTED_PLAN and not any(backwards for _, backwards in plan),
             "migration plan is not exactly ai_core.0001 + ai_core.0002", RunnerAborted)
    return executor


def _consume_one_use_release(connection, target: Target, expected_sha: str) -> None:
    """Spend release once in an independent durable autocommit connection.

    The existing AuditEvent.event_id UNIQUE constraint provides atomic replay
    prevention across processes, including after migration rollback. This
    only enforces consumption; owner issuance must be verified separately.
    """
    _require(target.name == "production" and bool(target.release_id),
             "production release ID missing", RunnerAborted)
    _require(bool(SHA40.fullmatch(expected_sha)), "expected SHA malformed", RunnerAborted)
    receipt_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://github.com/13640226/VORNEQ/c02-owner-release/{target.release_id}",
    )
    ledger = connection.copy(alias="c02_one_use_receipt")
    try:
        ledger.ensure_connection()
        _require(ledger.get_autocommit(), "one-use ledger must use autocommit", RunnerAborted)
        _check_identity(_snapshot(ledger), target, RunnerAborted)
        with ledger.cursor() as cur:
            cur.execute("SELECT to_regclass('audit_auditevent')")
            _require(cur.fetchone()[0] is not None,
                     "one-use audit ledger table missing", RunnerAborted)
            cur.execute(
                """
                INSERT INTO audit_auditevent
                    (event_id, schema_version, event_name, actor, target, outcome,
                     reason_code, correlation_id, metadata, retention_class, timestamp)
                VALUES (%s, 1, 'c02.production_migration_release_consumed',
                        %s::jsonb, %s::jsonb, 'granted',
                        'C02_ONE_USE_CONSUMED', %s, %s::jsonb, 'security', now())
                ON CONFLICT (event_id) DO NOTHING RETURNING event_id
                """,
                [
                    receipt_id,
                    json.dumps({"kind": "owner", "source": "sha_bound_release"}),
                    json.dumps({"service": PRODUCTION_SERVICE_ID, "database": target.database}),
                    str(receipt_id),
                    json.dumps({"sha": expected_sha, "release_id": target.release_id}),
                ],
            )
            _require(cur.fetchone() is not None,
                     "one-use release already consumed; retry denied", RunnerAborted)
    except RunnerAborted:
        raise
    except Exception as exc:
        # Lost acknowledgements may mean the receipt committed; never auto-retry.
        raise RunnerAborted(f"one-use ledger unavailable ({type(exc).__name__}); fail closed") from None
    finally:
        ledger.close()


def run(connection, target: Target, expected_sha: str, *, commit: bool,
        source_sha: Callable[[], str], out: Callable[[str], None] = print) -> dict:
    """Execute the guarded migration for an already *authorized* target."""
    if target.name == "production":
        _require(PRODUCTION_WRITE_ENABLED,
                 "C02 OPEN: production write path disabled", RunnerRefused)
        _require(bool(target.release_id),
                 "production one-use authorization missing", RunnerRefused)
    _require(connection.vendor == "postgresql", "PostgreSQL required")
    _require(not connection.in_atomic_block, "runner must own the outermost transaction")
    _require(MigrationRecorder(connection).has_table(), "django_migrations table missing")
    _check_identity(_snapshot(connection), target, RunnerRefused)
    _require(_state(connection) == (0, 0), "ai_core tables or history already present")

    try:
        with transaction.atomic(using=connection.alias):
            driver = connection.connection
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '2000ms'")
                cursor.execute("SET LOCAL statement_timeout = '60000ms'")
                cursor.execute("LOCK TABLE django_migrations IN SHARE ROW EXCLUSIVE MODE NOWAIT")
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [ADVISORY_LOCK_KEY])
                _require(cursor.fetchone()[0] is True, "advisory lock busy", RunnerAborted)
                cursor.execute("SELECT txid_current()")
                txid = cursor.fetchone()[0]
            before = _snapshot(connection)
            _check_identity(before, target, RunnerAborted)
            _require(before[6] == txid, "transaction id not assigned to this session", RunnerAborted)
            _require(_state(connection) == (0, 0), "pre-state changed after locking", RunnerAborted)
            executor = _exact_plan(connection)

            def same_session(label):
                current = _snapshot(connection)
                _require(connection.connection is driver and current == before,
                         f"session or transaction changed ({label})", RunnerAborted)

            same_session("before migrate")
            if target.name == "production":
                _consume_one_use_release(connection, target, expected_sha)
                # The release stays consumed even when this migration rolls back.
                same_session("after release consumption")
                _require(hmac.compare_digest(source_sha(), expected_sha),
                         "source SHA drift after release consumption", RunnerAborted)
                out("C02_STAGE_C: ONE_USE_RELEASE_CONSUMED")
            out("C02_STAGE_C: SHA, identity, locks and exact plan verified")
            executor.migrate([TARGET])
            same_session("after migrate")
            _require(hmac.compare_digest(source_sha(), expected_sha), "source SHA drift", RunnerAborted)
            _verify_schema(connection)
            _require(not MigrationExecutor(connection).migration_plan([TARGET]),
                     "migration plan not empty before commit", RunnerAborted)
            same_session("pre-commit")
            out("C02_STAGE_C: PRE_COMMIT_VERIFICATION PASS")
            if not commit:
                raise _Rehearsal()
    except _Rehearsal:
        out("C02_STAGE_C: rehearsal rolled back")
    except RunnerAborted:
        raise
    except Exception as exc:  # noqa: BLE001 - every error inside the transaction aborts it
        raise RunnerAborted(f"aborted and rolled back: {type(exc).__name__}") from exc

    with transaction.atomic(using=connection.alias):
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT 1")
            healthy = cursor.fetchone()[0] == 1
        state = _state(connection)
        if commit:
            _verify_schema(connection)
        pending = bool(MigrationExecutor(connection).migration_plan([TARGET]))
    expected_state, expected_pending = ((2, 2), False) if commit else ((0, 0), True)
    _require(healthy and state == expected_state and pending is expected_pending,
             "post-commit verification failed", RunnerAborted)
    out("C02_STAGE_C: POST_COMMIT_VERIFICATION PASS")
    return {"target": target.name, "committed": commit, "state": state, "pending": pending}
