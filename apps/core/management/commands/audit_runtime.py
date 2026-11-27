"""Read-only, secret-free runtime audit; no provider, cache or storage calls."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, router, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.models import Exists, OuterRef
from django.utils import timezone

TARGETS = {
    "staging": ("srv-dbm7dvc9v7es7393g70g", "vorneq_staging_db_9i8v"),
    "production": ("srv-dadn07eq1p3s73eccau0", "vorneq_production_db"),
}
LEDGER_DB = "vorneq_ai_ledger"
SHA = re.compile(r"[0-9a-f]{40}")
UNKNOWN = "NOT_VERIFIED"
FLAGS = (
    "VORNEQ_GLOBAL_AI_ENABLED", "VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED",
    "VORNEQ_AI_CORE_ENABLED", "VORNEQ_AI_PHASE_B_ENABLED",
    "VORNEQ_AI_STAGING_TRIAL_ENABLED", "VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS",
    "VORNEQ_AI_EMERGENCY_STOP", "VORNEQ_AI_LEDGER_ENABLED",
    "VORNEQ_AI_CONVERSATIONS_ENABLED", "VORNEQ_AI_CONTEXT_RETRIEVAL_ENABLED",
    "VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED", "VORNEQ_AI_RESPONSE_V3_ENABLED",
    "VORNEQ_AI_RESPONSE_V3_STAGE2_ENABLED",
    "VORNEQ_AI_CHAT_RECOVERY_ENABLED", "VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED",
    "VORNEQ_AI_CHAT_STREAMING_ENABLED", "VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED",
    "VORNEQ_AI_CHAT_JOBS_ENABLED", "VORNEQ_AI_CHAT_JOBS_PRODUCTION_ENABLED",
    "VORNEQ_AI_IMAGE_ENABLED", "VORNEQ_AI_IMAGE_UI_ENABLED",
    "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", "VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED",
    "VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS", "VORNEQ_AI_IMAGE_PRODUCTION_ENABLED",
    "VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED", "VORNEQ_AI_VOICE_ENABLED",
    "VORNEQ_AI_VOICE_PAID_CALLS_ENABLED",
)


def identity(environment, sha, local_test):
    """Reject wrong target before opening any database connection."""
    env = getattr(settings, "VORNEQ_ENV", None)
    if local_test:
        if (environment or sha or env != "development" or os.getenv("RENDER")
                or os.getenv("RENDER_SERVICE_ID") or os.getenv("RENDER_GIT_COMMIT")):
            raise CommandError("INVALID_LOCAL_IDENTITY")
        return {"environment": "development", "mode": "LOCAL_TEST"}
    if (environment not in TARGETS or env != environment or settings.DEBUG is not False
            or not isinstance(sha, str) or not SHA.fullmatch(sha)
            or os.getenv("RENDER_GIT_COMMIT") != sha
            or os.getenv("RENDER_SERVICE_ID") != TARGETS[environment][0]):
        raise CommandError("INVALID_HOSTED_IDENTITY")
    return {"environment": environment, "sha": sha,
            "service_id": TARGETS[environment][0], "mode": "HOSTED"}


def check_target(alias, environment, local_test):
    conn = connections[alias]
    name = str(conn.settings_dict["NAME"])
    if local_test:
        if conn.vendor == "sqlite":
            # Never create an absent SQLite database by opening it.
            if name != ":memory:" and not (
                name.startswith("file:memorydb_") and "mode=memory" in name
            ) and not Path(name).is_file():
                raise CommandError("LOCAL_DATABASE_MISSING")
        elif conn.vendor == "postgresql":
            if (conn.settings_dict.get("HOST") not in ("localhost", "127.0.0.1", "postgres")
                    or not name.startswith("test_")):
                raise CommandError("INVALID_LOCAL_POSTGRES_TARGET")
        else:
            raise CommandError("UNSUPPORTED_DATABASE")
    else:
        expected = TARGETS[environment][1] if alias == "default" else LEDGER_DB
        if conn.vendor != "postgresql" or name != expected:
            raise CommandError("INVALID_DATABASE_TARGET")
        if alias == "ai_ledger" and (
            not os.getenv("VORNEQ_AI_LEDGER_DATABASE_URL")
            or getattr(settings, "VORNEQ_AI_LEDGER_DB_NAME", None) != expected
        ):
            raise CommandError("INVALID_LEDGER_TARGET")
    return conn, name


@contextmanager
def readonly(alias, environment, local_test):
    conn, name = check_target(alias, environment, local_test)
    if conn.in_atomic_block or not conn.get_autocommit():
        raise CommandError("NESTED_TRANSACTION_REFUSED")
    if conn.vendor == "postgresql":
        with transaction.atomic(using=alias):
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '10s'")
                cur.execute("SELECT current_database(), current_setting('transaction_read_only')")
                if cur.fetchone() != (name, "on"):
                    raise CommandError("INVALID_DATABASE_SESSION")
            yield conn
    else:
        with conn.cursor() as cur:
            cur.execute("PRAGMA query_only")
            previous = cur.fetchone()[0]
            cur.execute("PRAGMA query_only = ON")
        try:
            with transaction.atomic(using=alias):
                with conn.cursor() as cur:
                    cur.execute("PRAGMA query_only")
                    if cur.fetchone()[0] != 1:
                        raise CommandError("SQLITE_READ_ONLY_FAILED")
                yield conn
        finally:
            with conn.cursor() as cur:
                cur.execute("PRAGMA query_only = ON" if previous else "PRAGMA query_only = OFF")


def migrations(conn):
    loader = MigrationLoader(conn, ignore_no_migrations=True)
    relevant = {key for key in loader.graph.nodes
                if router.allow_migrate(conn.alias, key[0]) is not False}
    applied = relevant.intersection(loader.applied_migrations)
    return {
        "known_count": len(relevant), "applied_count": len(applied),
        "pending_count": len(relevant - applied),
        "conflict_count": len(loader.detect_conflicts()),
        "ai_core_0005_applied": (
            ("ai_core", "0005_chat_job_v1") in applied if conn.alias == "default" else None
        ),
    }


def counts(qs, field, states):
    return {state: qs.filter(**{field: state}).count() for state in states}


def application_db(conn):
    from allauth.account.models import EmailAddress
    from django.contrib.auth import get_user_model
    from apps.ai_core.models import AIChatJob, AIImageJob, AIConversation, AIMessage
    from apps.core.models import UserIdentity, Identity

    result = {}
    chat = AIChatJob.objects.using("default")
    image = AIImageJob.objects.using("default")
    result["chat_jobs"] = counts(chat, "status", [s for s, _ in AIChatJob.STATES])
    result["expired_chat_leases"] = chat.filter(
        status__in=(AIChatJob.CLAIMED, AIChatJob.RUNNING, AIChatJob.CANCEL_REQUESTED),
        lease_until__lt=timezone.now()).count()
    result["image_jobs"] = counts(image, "status", [s for s, _ in AIImageJob.STATES])
    result["image_running_with_reservation"] = image.filter(
        status=AIImageJob.STATUS_RUNNING, reservation_id__isnull=False).count()
    result["image_uncertain_with_reservation"] = image.filter(
        status=AIImageJob.STATUS_UNCERTAIN, reservation_id__isnull=False).count()
    result["conversations"] = AIConversation.objects.using("default").count()
    result["messages"] = AIMessage.objects.using("default").count()
    users = get_user_model().objects.using("default").filter(is_active=True)
    verified = EmailAddress.objects.using("default").filter(
        user_id=OuterRef("pk"), primary=True, verified=True, email__iexact=OuterRef("email"))
    bindings = UserIdentity.objects.using("default").filter(
        user_id=OuterRef("pk"), identity__is_active=True, identity__kind=Identity.Kind.HUMAN)
    result["identity"] = {
        "active_accounts": users.count(),
        "verified_primary_matching": users.filter(Exists(verified)).count(),
        "active_human_bound": users.filter(Exists(bindings)).count(),
        "verified_unbound": users.filter(Exists(verified), ~Exists(bindings)).count(),
    }
    result["pgvector"] = "NOT_APPLICABLE"
    if conn.vendor == "postgresql":
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector'), "
                        "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            available, installed = cur.fetchone()
        result["pgvector"] = {"available": available, "installed": installed}
    return result


def ledger_db(conn, environment):
    from apps.ai_ledger.models import BudgetAccount, BudgetReservation
    # Inspect the accounts even when the paid-call gate is intentionally closed.
    # This is read-only observation, never authorization or reservation.
    def configured_id(name):
        try:
            return uuid.UUID(str(getattr(settings, name, "")))
        except (ValueError, TypeError):
            return None

    chat_id = configured_id("VORNEQ_AI_LEDGER_ID")
    image_id = configured_id("VORNEQ_AI_IMAGE_LEDGER_ID")
    result = {}
    for label, account_id in (("chat", chat_id), ("image", image_id)):
        if account_id is None:
            result[label] = {"status": "NOT_CONFIGURED"}
            continue
        if label == "image" and image_id == chat_id:
            result[label] = {"status": "ACCOUNT_NOT_INDEPENDENT"}
            continue
        if getattr(settings, "VORNEQ_AI_LEDGER_DB_NAME", None) != str(conn.settings_dict["NAME"]):
            result[label] = {"status": "INVALID_DATABASE_IDENTITY"}
            continue
        account = BudgetAccount.objects.using("ai_ledger").filter(ledger_id=account_id)
        row = account.values("emergency_stop", "total_allowance_micro", "safety_reserve_micro",
                             "consumed_before_micro", "reserved_micro", "finalized_micro",
                             "uncertain_micro").first()
        if row is None:
            result[label] = {"status": "ACCOUNT_MISSING"}
            continue
        reservations = BudgetReservation.objects.using("ai_ledger").filter(
            account__in=account, environment=environment)
        result[label] = {
            "status": "OBSERVED", "emergency_stop": row["emergency_stop"],
            "remaining_micro": row["total_allowance_micro"] - sum(
                row[k] for k in ("safety_reserve_micro", "consumed_before_micro",
                                 "reserved_micro", "finalized_micro", "uncertain_micro")),
            "reservations": counts(reservations, "status", [s for s, _ in BudgetReservation.STATUS]),
        }
    return result


def configuration(environment):
    from apps.ai_core import chat_jobs, streaming, request_recovery
    from apps.ai_core.views_global import global_ai_available
    from apps.ai_core.image_generation import policy as image
    from apps.ai_core.image_generation.storage import durable_storage_ready
    from apps.ai_core.voice.config import load_config, emergency_stop_active
    from apps.ai_core.management.commands.ai_gateway_report import _chat_limits_section

    flags = {name: getattr(settings, name, False) is True for name in FLAGS}
    follow_chat = flags["VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS"]
    follow_image = flags["VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS"]
    # Existing policy functions can read GitHub evidence. Do not call them in
    # follow-owner mode: an offline result must not pretend to verify release.
    chat = UNKNOWN if follow_chat and environment in TARGETS else global_ai_available()
    image_gate = UNKNOWN if follow_image and environment == "staging" else image.enabled()
    paid_image = UNKNOWN if follow_image and environment == "staging" else image.paid_provider_enabled()
    if flags["VORNEQ_AI_EMERGENCY_STOP"]:
        chat = image_gate = paid_image = False
    if not flags["VORNEQ_AI_IMAGE_ENABLED"]:
        image_gate = paid_image = False
    if not flags["VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED"]:
        paid_image = False
    limits = _chat_limits_section()
    prefix = "VORNEQ_AI_PRODUCTION" if environment == "production" else "VORNEQ_AI_STAGING"
    pin = getattr(settings, prefix + "_AUTHORIZED_SHA", "")
    approved_model = getattr(settings, prefix + "_APPROVED_MODEL", "")
    configured_model = os.getenv("VORNEQ_AI_PHASE_B_MODEL", "")
    release = os.getenv("RENDER_GIT_COMMIT", "")
    numeric = {k: limits[k] for k in (
        "context_window", "max_input_tokens", "effective_output_tokens",
        "pipeline_output_tokens", "max_history_tokens", "max_request_bytes",
        "max_message_characters", "effective_answer_chars", "max_attachment_bytes")
        if type(limits.get(k)) is int or limits.get(k) is None}
    backend = getattr(settings, "EMAIL_BACKEND", None)
    email = {
        "config.email_backends.ResendEmailBackend": "RESEND",
        "django.core.mail.backends.smtp.EmailBackend": "SMTP",
        "django.core.mail.backends.console.EmailBackend": "CONSOLE",
    }.get(backend, "OTHER")
    return {
        "flags": flags, "effective_policy": {
            "chat": chat, "streaming_flag": streaming.enabled(),
            "chat_jobs_flag": chat_jobs.enabled(), "recovery_flag": request_recovery.enabled(),
            "image_web": image_gate, "image_paid_web": paid_image,
            "image_production_paid": (
                UNKNOWN if environment == "production" and
                flags["VORNEQ_AI_IMAGE_PRODUCTION_ENABLED"] else False
            ),
            "voice_mock": load_config() is not None and not emergency_stop_active(),
            "image_storage_config_ready": durable_storage_ready(),
        },
        "limits": numeric,
        "release_predicates": {
            "configured_model_present": bool(configured_model),
            "approved_model_matches": bool(approved_model and approved_model == configured_model),
            "legacy_pin_matches": bool(SHA.fullmatch(release) and pin == release),
            "owner_authorization_present": bool(getattr(settings, prefix + "_OWNER_AUTH", "")),
        },
        "ledger_configured": limits.get("ledger_status") == "ENABLED",
        "redis_recovery_configured": (
            settings.CACHES.get("default", {}).get("BACKEND")
            == "django.core.cache.backends.redis.RedisCache" and bool(getattr(settings, "REDIS_URL", None))
        ),
        "email_backend": email,
        "resend_key_present": bool(os.getenv("RESEND_API_KEY")),
        "text_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "image_key_present": bool(os.getenv("VORNEQ_OPENAI_IMAGE_API_KEY")),
        "official_release_evidence": UNKNOWN,
        "worker_process_health": UNKNOWN,
        "provider_delivery": UNKNOWN,
    }


class Command(BaseCommand):
    help = "Audit runtime configuration and aggregate database state, without writes or provider calls."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--environment", choices=tuple(TARGETS))
        parser.add_argument("--expected-sha")
        parser.add_argument("--local-test", action="store_true")

    def handle(self, *args, **options):
        local = options["local_test"]
        env = options["environment"]
        target = identity(env, options["expected_sha"], local)
        # Preflight application target before any reads; ledger independently.
        check_target("default", env, local)
        report = {"identity": target, "status": "COMPLETE", "errors": []}
        sections = (
            ("configuration", lambda: configuration(target["environment"])),
            ("application_migrations", lambda: self.read_section("default", env, local, migrations)),
            ("application", lambda: self.read_section("default", env, local, application_db)),
            ("ledger_migrations", lambda: self.read_section("ai_ledger", env, local, migrations)),
            ("ledger", lambda: self.read_section(
                "ai_ledger", env, local, lambda conn: ledger_db(conn, target["environment"]))),
        )
        for name, builder in sections:
            try:
                report[name] = builder()
            except Exception:
                # Do not echo driver errors, settings, exception values or tracebacks.
                report[name] = {"status": UNKNOWN}
                report["errors"].append(name)
        if report["errors"]:
            report["status"] = "PARTIAL"
        self.stdout.write(json.dumps(report, sort_keys=True, indent=2))
        if report["errors"]:
            raise CommandError("AUDIT_INCOMPLETE")

    @staticmethod
    def read_section(alias, env, local, builder):
        with readonly(alias, env, local) as conn:
            return builder(conn)
