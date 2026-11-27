"""Proposed hosted 0006 execution boundary: independently authorized only.

The existing Render web deploy cannot be used as the new migration artifact.
This module implements a guarded candidate executor. The operational artifact
path must be independently verified and reviewed before use.
"""
from __future__ import annotations

import json
import uuid
from django.conf import settings
from apps.core import c02_operational_binding as binding
from apps.core import c02_message_feedback_0006_release as release
from apps.core import c02_owner_release as legacy
from apps.core.c02_message_feedback_0006_runner import Refused, Aborted, require

COMPATIBLE_LIVE_SHA = "e25be58999920a98481d58c15f42bcfb295308d5"
ARM_MODE = "ONE_USE_OWNER_RELEASE"
CLOSED_FLAGS = (
    "VORNEQ_GLOBAL_AI_ENABLED", "VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED",
    "VORNEQ_AI_CONVERSATIONS_ENABLED", "VORNEQ_AI_CHAT_JOBS_ENABLED",
    "VORNEQ_AI_CHAT_JOBS_PRODUCTION_ENABLED", "VORNEQ_AI_FEEDBACK_ENABLED",
)


def verify_context(environ, expected_environment, source_sha, live_sha, db_config,
                   actual_source_sha):
    """Pure check; no network or SQL, does not authorize migration."""
    require(isinstance(expected_environment, str) and expected_environment in release.TARGETS,
            "unknown hosted environment")
    require(isinstance(source_sha, str) and release.SHA.fullmatch(source_sha)
            and actual_source_sha == source_sha, "source SHA mismatch")
    require(live_sha == COMPATIBLE_LIVE_SHA and source_sha != live_sha
            and environ.get("RENDER_GIT_COMMIT") == live_sha,
            "live SHA not the reviewed V9.1 baseline")
    target = release.TARGETS[expected_environment]
    require(environ.get("VORNEQ_ENV") == expected_environment
            and getattr(settings, "VORNEQ_ENV", None) == expected_environment
            and settings.DEBUG is False
            and environ.get("RENDER_SERVICE_ID") == target.service,
            "hosted identity mismatch")
    require(environ.get("DJANGO_SETTINGS_MODULE") == "config.settings_render",
            "Render settings required")
    require(environ.get("VORNEQ_C02_0006_WRITE_MODE") == ARM_MODE
            and environ.get("VORNEQ_C02_0006_ARMED_SOURCE_SHA") == source_sha
            and environ.get("VORNEQ_C02_0006_ARMED_LIVE_SHA") == live_sha,
            "0006 write arm closed")
    for key in CLOSED_FLAGS:
        require(getattr(settings, key, None) is False
                and environ.get(key, "").lower() in ("", "false", "off", "0", "no"),
                "conversation writes and feedback must be stopped")
    require(db_config.get("ENGINE") == "django.db.backends.postgresql",
            "PostgreSQL required")
    url = environ.get("DATABASE_URL", "")
    try:
        bound = (binding.parse_url(url)["HOST"] == target.postgres
                 and binding.settings_match_url(db_config, url))
    except (ValueError, TypeError):
        bound = False
    require(bound and db_config.get("NAME") == target.database
            and db_config.get("USER") == target.login
            and str(db_config.get("PORT") or "5432") == "5432",
            "database resource binding mismatch")
    return target


def observe_owner(environ, *, environment, source_sha, live_sha, release_id):
    """Authenticate evidence only; not a permit to execute the hosted runner."""
    require(isinstance(release_id, str) and release.RELEASE_ID.fullmatch(release_id),
            "invalid release ID")
    auth = f"OWNER-AUTH-C02-0006-{environment.upper()}-{release_id} @ {source_sha}"
    require(environ.get("VORNEQ_C02_0006_MIGRATION_AUTH") == auth,
            "scoped authorization missing")
    try:
        return release.verify_live(environ, environment=environment, source_sha=source_sha,
                                   live_sha=live_sha, release_id=release_id)
    except legacy.OwnerReleaseDenied as exc:
        raise Refused("owner release denied: " + str(exc)) from None


def receipt_uuid(proof):
    """Stable across source revisions: a release ID cannot be replayed."""
    return uuid.uuid5(uuid.NAMESPACE_URL,
                      f"https://github.com/13640226/VORNEQ/pull/{release.ISSUE}/"
                      f"c02-0006/{proof.environment}/{proof.release_id}")


def receipt_payload(proof):
    """Secret-free receipt fields, not a database write."""
    require(isinstance(proof, release.Proof), "verified owner proof required", Aborted)
    target = release.TARGETS[proof.environment]
    event_id = receipt_uuid(proof)
    return {
        "event_id": event_id,
        "event_name": f"{proof.environment}.ai_feedback_0006_one_use_release_consumed",
        "actor": json.dumps({"kind": "github_owner", "comment_id": proof.comment_id}),
        "target": json.dumps({"service": target.service, "postgres_id": target.postgres,
                              "database": target.database}),
        "metadata": json.dumps({"release_id": proof.release_id,
                                "source_sha": proof.source_sha, "live_sha": proof.live_sha,
                                "backup_sha256": proof.backup_sha256,
                                "owner_body_sha256": proof.body_sha256}),
    }



def session_snapshot(connection, target, mode):
    """Pinned PostgreSQL identity for the same execution session."""
    with connection.cursor() as c:
        c.execute("SELECT pg_backend_pid(), current_database(), current_user, session_user, "
                  "inet_server_addr()::text, inet_server_port(), "
                  "current_setting('transaction_read_only'), pg_is_in_recovery(), "
                  "current_setting('server_version_num')::int / 10000, current_schema(), "
                  "txid_current_if_assigned()")
        row = tuple(c.fetchone())
    require(len(row) == 11 and isinstance(row[0], int)
            and row[1] == target.database and row[2] == target.role and row[3] == target.login
            and row[4] and row[5] == 5432 and row[6] == mode and row[7] is False
            and row[8] == 18 and row[9] == "public",
            "hosted PostgreSQL identity mismatch", Aborted)
    return row


def consume_receipt(connection, proof, target, initial):
    """Independent autocommit receipt, durable even if DDL rolls back."""
    payload = receipt_payload(proof)
    receipt = connection.copy(alias="c02_feedback_0006_receipt")
    try:
        receipt.ensure_connection()
        require(receipt.get_autocommit(), "receipt session not autocommit", Aborted)
        observed = session_snapshot(receipt, target, "off")
        require(observed[1:6] == initial[1:6], "receipt target differs", Aborted)
        with receipt.cursor() as c:
            c.execute("SELECT to_regclass('public.audit_auditevent')")
            require(c.fetchone()[0] is not None, "audit receipt table missing", Aborted)
            c.execute("""
                INSERT INTO public.audit_auditevent
                    (event_id, schema_version, event_name, actor, target, outcome,
                     reason_code, correlation_id, metadata, retention_class, timestamp)
                VALUES (%s, 1, %s, %s::jsonb, %s::jsonb, 'granted',
                        'C02_FEEDBACK_0006_RECEIPT', %s, %s::jsonb, 'security', now())
                ON CONFLICT (event_id) DO NOTHING RETURNING event_id
                """, [payload["event_id"], payload["event_name"], payload["actor"],
                       payload["target"], str(payload["event_id"]), payload["metadata"]])
            require(c.fetchone() is not None, "one-use release already consumed", Aborted)
    except Aborted:
        raise
    except Exception as exc:
        raise Aborted("receipt outcome uncertain: " + type(exc).__name__) from None
    finally:
        receipt.close()


def run_hosted(connection, *, environment, expected_sha, live_sha, release_id,
               artifact_sha, environ):
    """Candidate schema-first executor; no automatic enablement or deployment.

    The caller must be the separately verified checkout management command.
    Runtime feasibility still needs independent preflight and owner approval.
    """
    from django.db import transaction
    from apps.core import c02_message_feedback_0006_runner as core

    def context():
        return verify_context(environ, environment, expected_sha, live_sha,
                              connection.settings_dict, artifact_sha())

    target = context()
    require(connection.alias == "default" and connection.vendor == "postgresql",
            "default PostgreSQL only")
    def fresh_proof():
        try:
            observed = observe_owner(environ, environment=environment, source_sha=expected_sha,
                                     live_sha=live_sha, release_id=release_id)
            release.verify_main_sha(environ, expected_sha)
            return observed
        except legacy.OwnerReleaseDenied as exc:
            raise Refused("source authorization denied: " + str(exc)) from None

    proof = fresh_proof()
    require(not connection.in_atomic_block and connection.get_autocommit(),
            "outermost transaction required")
    with transaction.atomic(using=connection.alias):
        with connection.cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
            c.execute("SET LOCAL statement_timeout = '10s'")
        session_snapshot(connection, target, "on")
        require(core.state(connection) == (core.PRE_HISTORY, core.PRE_TABLES),
                "unexpected pre-state")
        core.exact_plan(connection)
    receipt_attempted = False
    try:
        with transaction.atomic(using=connection.alias):
            with connection.cursor() as c:
                c.execute("SET LOCAL lock_timeout = '2s'")
                c.execute("SET LOCAL statement_timeout = '60s'")
                c.execute("LOCK TABLE django_migrations IN SHARE ROW EXCLUSIVE MODE NOWAIT")
                c.execute("SELECT pg_try_advisory_xact_lock(%s)", [core.LOCK_KEY])
                require(c.fetchone()[0] is True, "migration lock busy", Aborted)
                c.execute("SELECT txid_current()")
                txn = c.fetchone()[0]
            driver = connection.connection
            initial = session_snapshot(connection, target, "off")
            require(initial[-1] == txn, "transaction mismatch", Aborted)
            require(core.state(connection) == (core.PRE_HISTORY, core.PRE_TABLES),
                    "pre-state drift", Aborted)
            executor = core.exact_plan(connection)

            def same_context():
                require(context() == target and connection.connection is driver
                        and session_snapshot(connection, target, "off") == initial,
                        "source, session or arm drift", Aborted)

            same_context()
            require(fresh_proof() == proof, "owner release changed", Aborted)
            same_context()
            receipt_attempted = True
            consume_receipt(connection, proof, target, initial)
            same_context()
            executor.migrate([core.TARGET])
            same_context()
            core.verify_schema(connection)
            require(fresh_proof() == proof, "owner release changed before commit", Aborted)
            same_context()
    except Refused as exc:
        if receipt_attempted:
            raise Aborted("owner/source refused after receipt attempt; do not retry") from None
        raise
    except Aborted:
        raise
    except Exception as exc:
        raise Aborted("migration aborted or outcome uncertain: " + type(exc).__name__) from None
    # Commit has happened; any failure now is uncertain, not a retry permit.
    try:
        with transaction.atomic(using=connection.alias):
            with connection.cursor() as c:
                c.execute("SET TRANSACTION READ ONLY")
                c.execute("SET LOCAL statement_timeout = '10s'")
            session_snapshot(connection, target, "on")
            core.verify_schema(connection)
    except Exception as exc:
        raise Aborted("post-commit verification failed; do not retry: " + type(exc).__name__) from None
    return {"environment": environment, "committed": True,
            "release_id": release_id, "deploy_authorized": False}
