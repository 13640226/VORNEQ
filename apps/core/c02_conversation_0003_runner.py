"""C02 guarded executor for exactly ai_core.0003_conversation.

Does NOT alter the existing 0001/0002 executor or its authorization contract.
Production requires a fresh, one-use owner proof scoped to 0003, the exact live
SHA, a verified backup, disabled AI writes, and same-session PostgreSQL checks.
A lab rehearsal rolls back. Deployment alone cannot authorize migration.
"""
from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass
from typing import Callable

from django.db import transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from apps.core import c02_operational_binding as binding
from apps.core import c02_owner_release as legacy
from apps.core import c02_conversation_0003_release as release
from apps.core import c02_stage_c_runner as previous

TARGET = ("ai_core", "0003_conversation")
PRE_HISTORY = ("0001_initial", "0002_aichatrequestguard")
POST_HISTORY = PRE_HISTORY + ("0003_conversation",)
PRE_TABLES = frozenset({"ai_core_stagingaibudgetday", "ai_core_aichatrequestguard"})
POST_TABLES = PRE_TABLES | frozenset({"ai_core_aiconversation", "ai_core_aimessage"})
EXPECTED_INDEXES = frozenset({
    "ai_conv_owner_list_idx", "ai_conv_deleted_idx",
    "ai_msg_conv_seq_idx", "ai_msg_status_time_idx",
})
EXPECTED_CONSTRAINTS = frozenset({
    "ai_msg_conv_seq_unique", "ai_msg_role_valid",
    "ai_msg_status_valid", "ai_msg_user_turn_plain",
})
ARM_MODE_KEY = "VORNEQ_C02_0003_WRITE_MODE"
ARM_SHA_KEY = "VORNEQ_C02_0003_ARMED_SHA"
ARM_MODE = "ONE_USE_OWNER_RELEASE"
AUTH_KEY = "VORNEQ_C02_0003_MIGRATION_AUTH"
AUTH_RE = re.compile(r"OWNER-AUTH-C02-0003-(?P<id>[A-Z0-9-]{6,60}) @ (?P<sha>[0-9a-f]{40})\Z")
LOCK_KEY = 62520261117


class Refused(Exception):
    """Preflight failure: no migration run."""


class Aborted(Exception):
    """Migration transaction aborted or verified state differs."""


class _Rehearsal(Exception):
    pass


def require(ok, reason, error=Refused):
    if not ok:
        raise error(reason)


def arm_open(environ, expected_sha):
    return bool(isinstance(expected_sha, str) and previous.SHA40.fullmatch(expected_sha)
                and environ.get(ARM_MODE_KEY) == ARM_MODE
                and environ.get(ARM_SHA_KEY) == expected_sha
                and environ.get("VORNEQ_ENV") == "production"
                and environ.get("RENDER_SERVICE_ID") == previous.PRODUCTION_SERVICE_ID
                and environ.get("RENDER_GIT_COMMIT") == expected_sha)


def _ai_writes_stopped(environ):
    return (str(environ.get("VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED", "")).lower()
            in ("", "false", "off", "0", "no")
            and str(environ.get("VORNEQ_AI_CONVERSATIONS_ENABLED", "")).lower()
            in ("", "false", "off", "0", "no"))


def authorize(target_name, environ, expected_sha, settings_dict, actual_sha):
    require(bool(isinstance(expected_sha, str) and previous.SHA40.fullmatch(expected_sha)),
            "malformed SHA")
    require(actual_sha == expected_sha, "source SHA mismatch")
    if target_name == "production":
        require(arm_open(environ, expected_sha), "0003 production write arm closed")
        require(_ai_writes_stopped(environ), "AI writes must be disabled for migration")
        auth = AUTH_RE.fullmatch(environ.get(AUTH_KEY, ""))
        require(bool(auth) and auth.group("sha") == expected_sha,
                "missing scoped SHA-bound 0003 migration authorization")
        url = environ.get("DATABASE_URL", "")
        try:
            valid_url = (bool(url)
                         and binding.classify_host(binding.parse_url(url)["HOST"]) == "INTERNAL_EXACT"
                         and binding.settings_match_url(settings_dict, url))
        except (ValueError, TypeError):
            valid_url = False
        require(valid_url, "database connection not bound to Render internal resource")
        require(settings_dict.get("NAME") == binding.EXPECTED_DATABASE
                and settings_dict.get("USER") == binding.EXPECTED_DATABASE_USER,
                "unexpected Production database settings")
        try:
            proof = release.verify_live(
                environ, expected_sha=expected_sha, release_id=auth.group("id"))
        except legacy.OwnerReleaseDenied as exc:
            raise Refused(f"owner release denied: {exc}") from None
        return previous.Target(
            "production", binding.EXPECTED_DATABASE, binding.EXPECTED_EXECUTION_ROLE,
            previous.PRODUCTION_PG_MAJOR, release_id=auth.group("id"),
            login_user=binding.EXPECTED_DATABASE_USER, owner_proof=proof,
        )
    if target_name == "lab":
        require(environ.get("VORNEQ_ENV") == "development", "lab requires development")
        require(environ.get("C02_CONV_0003_LAB") == "YES", "lab opt-in missing")
        require(not any(k.startswith("RENDER_") for k in environ),
                "Render context forbidden in lab")
        require(settings_dict.get("ENGINE", "").endswith("postgresql"),
                "disposable PostgreSQL required")
        require(settings_dict.get("HOST") in previous.LAB_HOSTS,
                "lab hostname not approved")
        name = settings_dict.get("NAME", "")
        require(bool(previous.LAB_DATABASE.fullmatch(name))
                and name != binding.EXPECTED_DATABASE, "lab database not disposable")
        return previous.Target("lab", name, settings_dict.get("USER", ""), None)
    raise Refused("unknown runner target")


def _history(connection):
    with connection.cursor() as c:
        c.execute("SELECT name FROM django_migrations WHERE app='ai_core' ORDER BY name")
        return tuple(row[0] for row in c.fetchall())


def _tables(connection):
    with connection.cursor() as c:
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema() "
                  "AND tablename LIKE 'ai_core_%'")
        return frozenset(row[0] for row in c.fetchall())


def _state(connection, history, tables, error=Aborted):
    require(_history(connection) == history, "unexpected ai_core history", error)
    require(_tables(connection) == tables, "unexpected ai_core table set", error)


def _plan(connection):
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    require(not executor.loader.detect_conflicts(), "conflicting migrations", Aborted)
    plan = executor.migration_plan([TARGET])
    entries = tuple((m.app_label, m.name, backwards) for m, backwards in plan)
    require(entries == ((TARGET[0], TARGET[1], False),),
            "migration plan must contain only ai_core.0003_conversation", Aborted)
    return executor


def _verify_schema(connection):
    _state(connection, POST_HISTORY, POST_TABLES)
    with connection.cursor() as c:
        c.execute("SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() "
                  "AND tablename IN ('ai_core_aiconversation','ai_core_aimessage')")
        indexes = {row[0] for row in c.fetchall()}
        c.execute(
            "SELECT conname FROM pg_constraint p JOIN pg_class t ON t.oid=p.conrelid "
            "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=current_schema() "
            "AND t.relname IN ('ai_core_aiconversation','ai_core_aimessage') "
            "AND p.convalidated"
        )
        constraints = {row[0] for row in c.fetchall()}
    require(EXPECTED_INDEXES <= indexes, "conversation indexes missing", Aborted)
    require(EXPECTED_CONSTRAINTS <= constraints, "conversation constraints missing", Aborted)


def run(connection, target, expected_sha, *, commit, source_sha: Callable[[], str],
        environ=None, out: Callable[[str], None] = print):
    environ = os.environ if environ is None else environ
    if target.name == "production":
        require(commit, "Production rehearsal forbidden; lab only")
        require(arm_open(environ, expected_sha) and _ai_writes_stopped(environ),
                "production migration arm closed or AI enabled")
        require(isinstance(target.owner_proof, legacy.VerifiedOwnerRelease)
                and target.owner_proof.sha == expected_sha
                and target.owner_proof.release_id == target.release_id,
                "fresh owner evidence required")
    require(connection.vendor == "postgresql", "PostgreSQL only")
    require(not connection.in_atomic_block, "outermost transaction required")
    require(MigrationRecorder(connection).has_table(), "migration recorder missing")
    previous._check_identity(previous._snapshot(connection), target, Refused)
    _state(connection, PRE_HISTORY, PRE_TABLES, Refused)
    require(source_sha() == expected_sha, "source SHA drift")

    try:
        with transaction.atomic(using=connection.alias):
            driver = connection.connection
            with connection.cursor() as c:
                c.execute("SET LOCAL lock_timeout = '2000ms'")
                c.execute("SET LOCAL statement_timeout = '60000ms'")
                c.execute("LOCK TABLE django_migrations IN SHARE ROW EXCLUSIVE MODE NOWAIT")
                c.execute("SELECT pg_try_advisory_xact_lock(%s)", [LOCK_KEY])
                require(c.fetchone()[0] is True, "migration advisory lock busy", Aborted)
                c.execute("SELECT txid_current()")
                txn = c.fetchone()[0]
            initial = previous._snapshot(connection)
            previous._check_identity(initial, target, Aborted)
            require(initial[6] == txn, "transaction continuity lost", Aborted)
            _state(connection, PRE_HISTORY, PRE_TABLES)
            executor = _plan(connection)

            def check_context(label):
                require(connection.connection is driver
                        and previous._snapshot(connection) == initial,
                        "transaction drift at " + label, Aborted)
                require(source_sha() == expected_sha, "source SHA drift", Aborted)

            def check_owner(label):
                require(arm_open(environ, expected_sha) and _ai_writes_stopped(environ),
                        "owner arm revoked at " + label, Aborted)
                try:
                    latest = release.verify_live(
                        environ, expected_sha=expected_sha, release_id=target.release_id)
                except legacy.OwnerReleaseDenied as exc:
                    raise Aborted(f"owner release denied at {label}: {exc}") from None
                require(latest == target.owner_proof, "owner proof changed", Aborted)

            check_context("pre-migrate")
            if target.name == "production":
                check_owner("pre-consumption")
                check_context("after owner verification")
                # Durable one-use receipt in a separate autocommit connection.
                # Consumption survives DDL rollback. Never automatically retry.
                previous._consume_one_use_release(connection, target, expected_sha)
                check_context("after consumption")
                out("C02_CONV_0003: ONE_USE_RELEASE_CONSUMED")
            executor.migrate([TARGET])
            check_context("post-migrate")
            _verify_schema(connection)
            require(not MigrationExecutor(connection).migration_plan([TARGET]),
                    "migration plan not empty before commit", Aborted)
            if target.name == "production":
                check_owner("pre-commit")
                check_context("post-attestation")
            out("C02_CONV_0003: PRE_COMMIT_VERIFICATION_PASS")
            if not commit:
                raise _Rehearsal()
    except _Rehearsal:
        out("C02_CONV_0003: LAB_ROLLBACK_COMPLETE")
    except (Refused, Aborted):
        raise
    except Exception as exc:
        raise Aborted(f"migration aborted and rolled back ({type(exc).__name__})") from None

    with transaction.atomic(using=connection.alias):
        with connection.cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
            c.execute("SELECT 1")
            require(c.fetchone()[0] == 1, "post-check connection failed", Aborted)
        if commit:
            _verify_schema(connection)
            pending = MigrationExecutor(connection).migration_plan([TARGET])
            require(not pending, "post-commit pending migration", Aborted)
        else:
            _state(connection, PRE_HISTORY, PRE_TABLES)
            pending = MigrationExecutor(connection).migration_plan([TARGET])
            require(len(pending) == 1 and pending[0][0].app_label == TARGET[0]
                    and pending[0][0].name == TARGET[1] and not pending[0][1],
                    "lab rehearsal did not rollback", Aborted)
    out("C02_CONV_0003: POST_COMMIT_VERIFICATION_PASS")
    return {"target": target.name, "committed": commit, "pending": not commit}
