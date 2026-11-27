"""C02 0006 exact-plan disposable rehearsal core.

The old deployed web SHA does not contain 0006. A separate attested execution
runtime must be independently verified before hosted use.
Never reuse the 0003/0004 grants or bypass a deployment/DB guard.
"""
from __future__ import annotations

import os
import re
from django.conf import settings
from django.db import transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from apps.core.c02_stage_c_runner import LAB_HOSTS, LAB_DATABASE

TARGET = ("ai_core", "0006_message_feedback")
PRE_HISTORY = ("0001_initial", "0002_aichatrequestguard", "0003_conversation",
               "0004_image_generation_job_v1", "0005_chat_job_v1")
POST_HISTORY = PRE_HISTORY + (TARGET[1],)
TABLE = "ai_core_aimessagefeedback"
PRE_TABLES = frozenset({"ai_core_stagingaibudgetday", "ai_core_aichatrequestguard",
                       "ai_core_aiconversation", "ai_core_aimessage",
                       "ai_core_aiimagejob", "ai_core_aiimagedailyquota",
                       "ai_core_aichatjob"})
LOCK_KEY = 202611270006


class Refused(Exception):
    pass


class Aborted(Exception):
    pass


class _Rollback(Exception):
    pass


def require(ok, message, error=Refused):
    if not ok:
        raise error(message)


def guard(connection, expected_sha, source_sha, environ):
    """No connection or network operation before these positive checks."""
    require(isinstance(expected_sha, str) and re.fullmatch(r"[0-9a-f]{40}", expected_sha),
            "invalid expected SHA")
    require(environ.get("VORNEQ_ENV") == "development"
            and getattr(settings, "VORNEQ_ENV", None) == "development",
            "hosted 0006 execution unavailable")
    require(not any(k.startswith("RENDER_") for k in environ), "Render context forbidden")
    require(environ.get("C02_FEEDBACK_0006_LAB") == "YES", "explicit lab opt-in required")
    require(connection.alias == "default" and connection.vendor == "postgresql",
            "default PostgreSQL lab only")
    cfg = connection.settings_dict
    require(cfg.get("HOST") in LAB_HOSTS and LAB_DATABASE.fullmatch(cfg.get("NAME", "")),
            "disposable database required")
    require(not cfg.get("OPTIONS"), "custom connection options refused")
    require(not connection.in_atomic_block and connection.get_autocommit(),
            "outermost transaction required")
    require(source_sha() == expected_sha, "source SHA mismatch")


def snapshot(connection, mode):
    with connection.cursor() as c:
        c.execute("SELECT pg_backend_pid(), current_database(), current_user, session_user, "
                  "inet_server_addr()::text, inet_server_port(), "
                  "current_setting('transaction_read_only'), pg_is_in_recovery(), "
                  "current_setting('server_version_num')::int / 10000, current_schema(), "
                  "txid_current_if_assigned()")
        row = tuple(c.fetchone())
    cfg = connection.settings_dict
    require(row[1] == cfg["NAME"] and row[2] == row[3] == cfg["USER"]
            and row[4] and row[5] == int(cfg.get("PORT") or 5432)
            and row[6] == mode and row[7] is False and row[8] >= 16
            and row[9] == "public", "lab session identity mismatch", Aborted)
    return row


def state(connection):
    require(MigrationRecorder(connection).has_table(), "migration recorder missing")
    with connection.cursor() as c:
        c.execute("SELECT name FROM django_migrations WHERE app='ai_core' ORDER BY name")
        history = tuple(r[0] for r in c.fetchall())
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                  "AND left(tablename, 8)='ai_core_'")
        tables = frozenset(r[0] for r in c.fetchall())
    return history, tables


def exact_plan(connection):
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    require(not executor.loader.detect_conflicts(), "migration graph conflict", Aborted)
    plan = tuple((m.app_label, m.name, reverse)
                 for m, reverse in executor.migration_plan([TARGET]))
    require(plan == (("ai_core", TARGET[1], False),), "not exactly forward 0006", Aborted)
    return executor


def verify_schema(connection, *, empty=True):
    require(state(connection) == (POST_HISTORY, PRE_TABLES | {TABLE}),
            "post-state differs", Aborted)
    with connection.cursor() as c:
        c.execute("SELECT column_name, data_type, is_nullable, character_maximum_length "
                  "FROM information_schema.columns WHERE table_schema='public' "
                  "AND table_name=%s", [TABLE])
        cols = set(c.fetchall())
        require(cols == {("message_id", "uuid", "NO", None),
                         ("rating", "character varying", "NO", 7),
                         ("created_at", "timestamp with time zone", "NO", None),
                         ("updated_at", "timestamp with time zone", "NO", None)},
                "feedback columns differ", Aborted)
        c.execute("SELECT contype, conname, convalidated, "
                  "pg_get_constraintdef(oid), confdeltype, "
                  "confrelid = to_regclass('public.ai_core_aimessage') "
                  "FROM pg_constraint WHERE conrelid=to_regclass(%s) AND contype <> 'n'", ["public."+TABLE])
        constraints = c.fetchall()
        require(len(constraints) == 3 and all(r[2] for r in constraints),
                "feedback constraints differ", Aborted)
        require(any(r[0] == "p" and r[3] == "PRIMARY KEY (message_id)" for r in constraints),
                "feedback primary key missing", Aborted)
        require(any(r[0] == "f" and r[4] == "a" and r[5]
                    and r[3].startswith("FOREIGN KEY (message_id) REFERENCES ai_core_aimessage(id)")
                    for r in constraints), "feedback FK differs", Aborted)
        require(any(r[0] == "c" and r[1] == "ai_msg_feedback_rating_valid"
                    and "like" in r[3] and "dislike" in r[3] for r in constraints),
                "feedback check missing", Aborted)
        if empty:
            c.execute("SELECT count(*) FROM public.ai_core_aimessagefeedback")
            require(c.fetchone()[0] == 0, "new feedback table not empty", Aborted)
    require(not MigrationExecutor(connection).migration_plan([TARGET]),
            "0006 still pending", Aborted)


def run(connection, expected_sha, *, source_sha, mode="inspect", environ=None):
    """Inspect or rollback rehearsal; lab commit is explicit, never hosted."""
    environ = os.environ if environ is None else environ
    require(mode in ("inspect", "rehearse", "lab_commit"), "unknown mode")
    guard(connection, expected_sha, source_sha, environ)
    if mode == "inspect":
        with transaction.atomic(using=connection.alias):
            with connection.cursor() as c:
                c.execute("SET TRANSACTION READ ONLY")
                c.execute("SET LOCAL statement_timeout = '10s'")
            snapshot(connection, "on")
            require(state(connection) == (PRE_HISTORY, PRE_TABLES), "unexpected pre-state")
            exact_plan(connection)
        return {"mode": mode, "committed": False, "hosted_authorized": False}
    try:
        with transaction.atomic(using=connection.alias):
            with connection.cursor() as c:
                c.execute("SET LOCAL lock_timeout = '2s'")
                c.execute("SET LOCAL statement_timeout = '60s'")
                c.execute("LOCK TABLE django_migrations IN SHARE ROW EXCLUSIVE MODE NOWAIT")
                c.execute("SELECT pg_try_advisory_xact_lock(%s)", [LOCK_KEY])
                require(c.fetchone()[0] is True, "migration lock busy", Aborted)
                c.execute("SELECT txid_current()")
                txn = c.fetchone()[0]
            driver = connection.connection
            before = snapshot(connection, "off")
            require(before[-1] == txn, "transaction identity mismatch", Aborted)
            require(state(connection) == (PRE_HISTORY, PRE_TABLES), "unexpected pre-state", Aborted)
            executor = exact_plan(connection)
            require(source_sha() == expected_sha, "source SHA drift", Aborted)
            executor.migrate([TARGET])
            require(connection.connection is driver and snapshot(connection, "off") == before
                    and source_sha() == expected_sha, "session or source drift", Aborted)
            verify_schema(connection)
            if mode == "rehearse":
                raise _Rollback()
    except _Rollback:
        pass
    except (Refused, Aborted):
        raise
    except Exception as exc:
        raise Aborted("migration transaction failed or uncertain: " + type(exc).__name__) from None
    with transaction.atomic(using=connection.alias):
        with connection.cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
            c.execute("SET LOCAL statement_timeout = '10s'")
        snapshot(connection, "on")
        if mode == "lab_commit":
            verify_schema(connection)
        else:
            require(state(connection) == (PRE_HISTORY, PRE_TABLES), "rollback verification failed", Aborted)
            exact_plan(connection)
    return {"mode": mode, "committed": mode == "lab_commit", "hosted_authorized": False}
