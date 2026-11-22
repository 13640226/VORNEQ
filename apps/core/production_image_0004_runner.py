"""Dedicated Production ai_core.0004 migration executor; FAIL CLOSED.

This is NOT a generic migrate permission. No Staging path. An exact,
fresh GitHub owner comment and a durable one-use receipt are mandatory for
--commit. Without --commit all SQL is read-only; ordinary migration workflows
and db_target_guard remain hard-stopped.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from apps.core import c02_owner_release as legacy
from apps.core import production_image_0004_release as release
from apps.core import production_image_0004_preflight as preflight

TARGET = ("ai_core", "0004_image_generation_job_v1")
PRE_HISTORY = ("0001_initial", "0002_aichatrequestguard", "0003_conversation")
POST_HISTORY = PRE_HISTORY + ("0004_image_generation_job_v1",)
PRE_TABLES = frozenset({
    "ai_core_stagingaibudgetday", "ai_core_aichatrequestguard",
    "ai_core_aiconversation", "ai_core_aimessage",
})
POST_TABLES = PRE_TABLES | frozenset({
    "ai_core_aiimagedailyquota", "ai_core_aiimagejob",
})
INDEXES = frozenset({"ai_image_owner_day_idx", "ai_image_queue_idx"})
ARM_MODE = "ONE_USE_OWNER_RELEASE"
ARM_MODE_KEY = "VORNEQ_PROD_IMAGE_0004_WRITE_MODE"
ARM_SHA_KEY = "VORNEQ_PROD_IMAGE_0004_ARMED_SHA"
AUTH_KEY = "VORNEQ_PROD_IMAGE_0004_MIGRATION_AUTH"
_SHA = re.compile(r"[0-9a-f]{40}\Z")
AUTH = re.compile(
    r"OWNER-AUTH-PRODUCTION-AI-0004-(?P<id>[A-Z0-9-]{8,60}) @ (?P<sha>[0-9a-f]{40})\Z"
)
LOCK_KEY = 202611220004


class Refused(Exception):
    """Refused before irreversible migration execution."""


class Aborted(Exception):
    """Uncertain outcome or aborted/rolled-back migration."""


@dataclass(frozen=True)
class ApprovedTarget:
    release_id: str
    proof: legacy.VerifiedOwnerRelease


def require(ok, reason, kind=Refused):
    if not ok:
        raise kind(reason)


def base_context(environ, expected_sha, db_config, *, require_arm=False):
    """Fail closed before SQL or network; use the same pinned Production binding."""
    try:
        preflight.check_context(environ, expected_sha, db_config)
    except preflight.PreflightDenied as exc:
        raise Refused(str(exc)) from None
    if require_arm:
        require(arm_open(environ, expected_sha), "production owner release arm closed")
        for key in ("VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED", "VORNEQ_AI_CONVERSATIONS_ENABLED"):
            require(getattr(settings, key, False) is False
                    and environ.get(key, "").lower() in ("", "false", "off", "0", "no"),
                    "Production chat and conversation writes must be stopped")


def arm_open(environ, expected_sha):
    return (isinstance(expected_sha, str) and _SHA.fullmatch(expected_sha) is not None
            and environ.get(ARM_MODE_KEY) == ARM_MODE
            and environ.get(ARM_SHA_KEY) == expected_sha
            and environ.get("VORNEQ_ENV") == "production"
            and environ.get("RENDER_SERVICE_ID") == release.SERVICE
            and environ.get("RENDER_GIT_COMMIT") == expected_sha)


def authorize(environ, expected_sha, db_config):
    base_context(environ, expected_sha, db_config, require_arm=True)
    match = AUTH.fullmatch(environ.get(AUTH_KEY, ""))
    require(match is not None and match.group("sha") == expected_sha,
            "missing exact SHA-bound one-use owner authorization")
    try:
        proof = release.verify_live(
            environ, expected_sha=expected_sha, release_id=match.group("id")
        )
    except legacy.OwnerReleaseDenied as exc:
        raise Refused("authenticated GitHub owner permit denied: " + str(exc)) from None
    require(proof.backup_sha256 == environ.get("VORNEQ_PROD_IMAGE_0004_BACKUP_SHA256"),
            "backup evidence changed")
    return ApprovedTarget(match.group("id"), proof)


def snapshot(connection):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT pg_backend_pid(), current_database(), current_user, "
            "session_user, inet_server_addr()::text, inet_server_port(), "
            "current_setting('transaction_read_only'), pg_is_in_recovery(), "
            "current_setting('server_version_num')::int / 10000, "
            "txid_current_if_assigned()"
        )
        return tuple(cur.fetchone())


def check_identity(observed, readonly, kind=Refused):
    require(len(observed) == 10, "incomplete database identity", kind)
    pid, db, user, session_user, address, port, mode, standby, major, txn = observed
    require(isinstance(pid, int) and db == release.DATABASE
            and user == release.ROLE and session_user == release.LOGIN
            and address and port == 5432 and standby is False and major == 18
            and mode == ("on" if readonly else "off"),
            "PostgreSQL runtime identity mismatch", kind)


def state(connection):
    with connection.cursor() as c:
        c.execute("SELECT name FROM django_migrations WHERE app = 'ai_core' ORDER BY name")
        history = tuple(row[0] for row in c.fetchall())
        c.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
            "AND tablename LIKE 'ai_core_%'"
        )
        tables = frozenset(row[0] for row in c.fetchall())
    return history, tables


def exact_plan(connection):
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    require(not executor.loader.detect_conflicts(), "migration graph conflict")
    items = tuple(
        (mig.app_label, mig.name, backwards)
        for mig, backwards in executor.migration_plan([TARGET])
    )
    require(items == ((TARGET[0], TARGET[1], False),),
            "migration plan is not exactly the single ai_core.0004")
    return executor


def assert_post_state(connection, error=Aborted):
    history, tables = state(connection)
    require(history == POST_HISTORY and tables == POST_TABLES,
            "unexpected post-migration history or tables", error)
    with connection.cursor() as c:
        c.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() "
            "AND tablename = 'ai_core_aiimagejob'"
        )
        indexes = frozenset(row[0] for row in c.fetchall())
        c.execute("SELECT count(*) FROM ai_core_aiimagejob")
        jobs = c.fetchone()[0]
        c.execute("SELECT count(*) FROM ai_core_aiimagedailyquota")
        quota = c.fetchone()[0]
    require(INDEXES <= indexes and jobs == 0 and quota == 0,
            "expected new image tables and indexes missing/dirty", error)


def inspect(connection, expected_sha, *, environ=None, out=print):
    """Read-only same-connection preflight; never authorizes writes."""
    environ = os.environ if environ is None else environ
    base_context(environ, expected_sha, connection.settings_dict)
    require(connection.vendor == "postgresql" and not connection.in_atomic_block
            and connection.get_autocommit(), "outermost PostgreSQL read-only preflight required")
    with transaction.atomic(using=connection.alias):
        with connection.cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
            c.execute("SET LOCAL statement_timeout = '8000ms'")
        check_identity(snapshot(connection), True)
        require(MigrationRecorder(connection).has_table(), "migration recorder missing")
        require(state(connection) == (PRE_HISTORY, PRE_TABLES),
                "unrecognized current ai_core state")
        exact_plan(connection)
    out("PRODUCTION_IMAGE_0004_PREFLIGHT: IDENTITY_AND_PLAN_PASS")
    out("PRODUCTION_IMAGE_0004_MIGRATION_GO: NO; READ_ONLY")
    return {"safe_to_review": True, "committed": False}


def consume_one_use_receipt(connection, target, expected_sha, *, expected_server=None):
    """Durable autocommit receipt; survives DDL rollback. No automatic retry."""
    receipt_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://github.com/13640226/VORNEQ/issues/{release.ISSUE}/production-image-0004-release/{target.release_id}",
    )
    ledger = connection.copy(alias="production_image_0004_receipt")
    try:
        ledger.ensure_connection()
        require(ledger.get_autocommit(), "receipt session not in autocommit", Aborted)
        observed = snapshot(ledger)
        check_identity(observed, False, Aborted)
        require(expected_server is not None and observed[4] == expected_server,
                "receipt database server differs from locked session", Aborted)
        with ledger.cursor() as c:
            c.execute("SELECT to_regclass('public.audit_auditevent')")
            require(c.fetchone()[0] is not None, "audit receipt table missing", Aborted)
            c.execute(
                """
                INSERT INTO audit_auditevent
                    (event_id, schema_version, event_name, actor, target, outcome,
                     reason_code, correlation_id, metadata, retention_class, timestamp)
                VALUES (
                    %s, 1, 'production.ai_image_0004_one_use_release_consumed',
                    %s::jsonb, %s::jsonb, 'granted',
                    'PRD_IMAGE_0004_RECEIPT', %s, %s::jsonb, 'security', now()
                )
                ON CONFLICT (event_id) DO NOTHING RETURNING event_id
                """,
                [
                    receipt_id,
                    json.dumps({"kind": "github_owner", "comment_id": target.proof.comment_id}),
                    json.dumps({"service": release.SERVICE, "postgres_id": release.POSTGRES,
                                "database": release.DATABASE}),
                    str(receipt_id),
                    json.dumps({"release_id": target.release_id,
                                "sha": expected_sha,
                                "backup_sha256": target.proof.backup_sha256,
                                "owner_body_sha256": target.proof.body_sha256}),
                ],
            )
            require(c.fetchone() is not None, "one-use release already consumed", Aborted)
    except Aborted:
        raise
    except Exception as exc:
        raise Aborted("one-use receipt ambiguous/unavailable: " + type(exc).__name__) from None
    finally:
        ledger.close()


def apply_once(connection, target, expected_sha, *, environ=None, out=print):
    """Apply only the one named Production migration inside guarded transaction."""
    environ = os.environ if environ is None else environ
    require(isinstance(target, ApprovedTarget) and isinstance(target.proof, legacy.VerifiedOwnerRelease), "owner permit not verified")
    base_context(environ, expected_sha, connection.settings_dict, require_arm=True)
    require(target.proof.sha == expected_sha and target.proof.release_id == target.release_id,
            "owner proof scope mismatch")
    require(connection.vendor == "postgresql" and not connection.in_atomic_block
            and connection.get_autocommit(), "outermost PostgreSQL transaction required")
    require(MigrationRecorder(connection).has_table(), "migration recorder missing")
    check_identity(snapshot(connection), False)
    require(state(connection) == (PRE_HISTORY, PRE_TABLES),
            "one-use migration already applied or wrong pre-state")
    try:
        with transaction.atomic(using=connection.alias):
            driver = connection.connection
            with connection.cursor() as c:
                c.execute("SET LOCAL lock_timeout = '2000ms'")
                c.execute("SET LOCAL statement_timeout = '60000ms'")
                c.execute("LOCK TABLE django_migrations IN SHARE ROW EXCLUSIVE MODE NOWAIT")
                c.execute("SELECT pg_try_advisory_xact_lock(%s)", [LOCK_KEY])
                require(c.fetchone()[0] is True, "one-use migration lock busy", Aborted)
                c.execute("SELECT txid_current()")
                txid = c.fetchone()[0]
            initial = snapshot(connection)
            check_identity(initial, False, Aborted)
            require(initial[-1] == txid, "transaction identity changed", Aborted)
            require(state(connection) == (PRE_HISTORY, PRE_TABLES),
                    "pre-state drift", Aborted)
            executor = exact_plan(connection)

            def same_session(label):
                require(connection.connection is driver
                        and snapshot(connection) == initial,
                        "session/transaction drift: " + label, Aborted)
                try:
                    base_context(environ, expected_sha, connection.settings_dict, require_arm=True)
                except Refused as exc:
                    raise Aborted("owner arm revoked or context changed: " + label) from exc

            def verify_owner(label):
                try:
                    fresh = release.verify_live(
                        environ, expected_sha=expected_sha, release_id=target.release_id
                    )
                except legacy.OwnerReleaseDenied:
                    raise Aborted("owner release invalid at " + label) from None
                require(fresh == target.proof, "owner release changed: " + label, Aborted)

            same_session("pre-consume")
            verify_owner("pre-consume")
            same_session("post-owner-pre-consume")
            consume_one_use_receipt(connection, target, expected_sha, expected_server=initial[4])
            out("PRODUCTION_IMAGE_0004_ONE_USE_RECEIPT_CONSUMED")
            same_session("pre-migrate")
            verify_owner("pre-migrate")
            same_session("post-owner-pre-migrate")
            executor.migrate([TARGET])
            same_session("post-migrate")
            assert_post_state(connection)
            require(not MigrationExecutor(connection).migration_plan([TARGET]),
                    "migration still pending before commit", Aborted)
            verify_owner("pre-commit")
            same_session("pre-commit")
            out("PRODUCTION_IMAGE_0004_PRECOMMIT_PASS")
    except (Refused, Aborted):
        raise
    except Exception as exc:
        raise Aborted("production migration rolled back or uncertain: "
                      + type(exc).__name__) from None
    with transaction.atomic(using=connection.alias):
        with connection.cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
        check_identity(snapshot(connection), True, Aborted)
        assert_post_state(connection)
        require(not MigrationExecutor(connection).migration_plan([TARGET]),
                "post-commit migration pending", Aborted)
    out("PRODUCTION_IMAGE_0004_COMMITTED_VERIFIED")
    return {"committed": True, "release_id": target.release_id}
