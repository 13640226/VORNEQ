"""Read-only preflight for the paid image feature; never authorizes activation.

No writes, migrations, OpenAI calls, or storage network calls are performed.
Even a PASS here is not a deployment permit: independent proof of private
bucket access, worker isolation, external spend limit and one-use authorization
is required.
"""
from __future__ import annotations

import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections, transaction
from django.db.migrations.recorder import MigrationRecorder

from apps.ai_core.image_generation import policy
from apps.ai_core.image_generation.storage import durable_storage_ready

STAGING_SERVICE = "srv-dbm7dvc9v7es7393g70g"
STAGING_DB_NAME = "vorneq_staging_db_9i8v"
IMAGE_MIGRATION = ("ai_core", "0004_image_generation_job_v1")


def _check_staging_db() -> tuple[bool, bool, str]:
    """Guard DB identity before checking migration history."""
    conn = connections["default"]
    if conn.vendor != "postgresql":
        return False, False, "not_postgresql"
    with transaction.atomic(using="default"):
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SELECT current_database()")
            actual = cursor.fetchone()[0]
            if actual != STAGING_DB_NAME:
                return False, False, "wrong_database"
        applied = IMAGE_MIGRATION in MigrationRecorder(conn).applied_migrations()
    return True, bool(applied), "ok"


def _check_image_ledger() -> tuple[bool, bool, bool, str]:
    """Read only the dedicated account; fail closed on missing identity."""
    from apps.ai_ledger.models import BudgetAccount

    try:
        config = policy.image_ledger_config()  # rejects reuse of chat account
    except Exception:
        return False, False, False, "image_ledger_not_configured"
    conn = connections["ai_ledger"]
    if conn.vendor != "postgresql":
        return True, False, False, "ledger_not_postgresql"
    try:
        with transaction.atomic(using="ai_ledger"):
            with conn.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '8s'")
                cursor.execute("SELECT current_database()")
                if cursor.fetchone()[0] != config.expected_db_name:
                    return True, False, False, "wrong_ledger_database"
            account = (BudgetAccount.objects.using("ai_ledger")
                       .filter(ledger_id=config.ledger_id)
                       .values(
                           "currency", "model_id", "allowed_environments",
                           "emergency_stop", "total_allowance_micro",
                           "safety_reserve_micro", "consumed_before_micro",
                           "reserved_micro", "finalized_micro",
                           "uncertain_micro", "input_price_micro_per_mtok",
                           "output_price_micro_per_mtok",
                       ).first())
        if account is None:
            return True, True, False, "image_account_missing"
        remaining = (
            account["total_allowance_micro"] - account["safety_reserve_micro"]
            - account["consumed_before_micro"] - account["reserved_micro"]
            - account["finalized_micro"] - account["uncertain_micro"]
        )
        valid = (
            account["currency"] == "USD"
            and account["model_id"] == getattr(settings, "VORNEQ_AI_IMAGE_MODEL", "")
            and "staging" in account["allowed_environments"].split(",")
            and not account["emergency_stop"]
            and remaining > 0
            and account["input_price_micro_per_mtok"] > 0
            and account["output_price_micro_per_mtok"] > 0
        )
        return True, True, bool(valid), "ok" if valid else "account_unready"
    except Exception:
        return True, False, False, "ledger_check_failed"


def collect_image_paid_preflight() -> dict:
    """Never emits tokens, URLs, usernames, image prompts or account balances."""
    env = getattr(settings, "VORNEQ_ENV", "")
    is_staging = (
        env == "staging"
        and settings.DEBUG is False
        and os.environ.get("RENDER_SERVICE_ID") == STAGING_SERVICE
    )
    runtime_sha = os.environ.get("RENDER_GIT_COMMIT", "")
    authorized_sha = getattr(settings, "VORNEQ_AI_IMAGE_AUTHORIZED_SHA", "")
    sha_ok = (
        len(runtime_sha) == 40
        and runtime_sha == authorized_sha
        and bool(policy._SHA.fullmatch(runtime_sha))
    )
    checks = {
        "staging_runtime_identity": bool(is_staging),
        "authorized_image_sha": bool(sha_ok),
        "owner_and_user_allowlist": bool(
            policy._OWNER.fullmatch(
                str(getattr(settings, "VORNEQ_AI_IMAGE_OWNER_AUTH", ""))
            ) and policy._ids()
        ),
        "private_storage_configured": bool(durable_storage_ready()),
        "api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "image_model_supported": getattr(settings, "VORNEQ_AI_IMAGE_MODEL", "") in policy.MODELS,
        "provider_openai_selected": getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "") == "openai",
        "output_bound_set": 0 < getattr(settings, "VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND", 0) <= 10_000_000,
        "daily_money_cap_set": getattr(settings, "VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD", 0) > 0,
        "daily_request_cap_set": 0 < getattr(settings, "VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS", 0) <= 50,
        "global_request_cap_set": 0 < getattr(settings, "VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS", 0) <= 500,
        "image_feature_currently_enabled": bool(getattr(settings, "VORNEQ_AI_IMAGE_ENABLED", False)),
        "paid_calls_currently_enabled": bool(getattr(settings, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", False)),
    }
    results = {
        "mode": "STRICT_READ_ONLY",
        "scope": "VORNEQ_STAGING_IMAGE_PAID",
        "checks": checks,
        "db_result": "not_checked",
        "ledger_result": "not_checked",
        "requires_external_verification": [
            "backup_and_restore_freshness",
            "single_use_migration_authorization",
            "private_bucket_acl_and_signed_url_test",
            "independent_provider_spend_limit",
            "approved_price_and_worst_case_image_cost",
            "worker_service_isolation",
            "live_mock_e2e_after_migration",
        ],
        "authorization": "NO_GO",
    }
    # Do not query any DB when this isn't positively identified as Staging.
    if not is_staging:
        results["db_result"] = "staging_identity_required"
        results["ledger_result"] = "staging_identity_required"
        return results
    try:
        db_correct, migrated, db_result = _check_staging_db()
    except Exception:
        db_correct, migrated, db_result = False, False, "db_check_failed"
    checks["staging_database_identity"] = db_correct
    checks["image_migration_0004_applied"] = migrated
    results["db_result"] = db_result
    # Ledger lookup is read-only, on a different verified DB alias.
    ledger_configured, ledger_db_correct, ledger_account, ledger_result = _check_image_ledger()
    checks["distinct_image_ledger_configured"] = ledger_configured
    checks["image_ledger_database_identity"] = ledger_db_correct
    checks["image_ledger_account_ready"] = ledger_account
    results["ledger_result"] = ledger_result
    return results


class Command(BaseCommand):
    help = "Fail-closed, read-only paid image staging preflight; never authorizes activation."

    def handle(self, *args, **options):
        report = collect_image_paid_preflight()
        self.stdout.write(json.dumps(report, sort_keys=True, separators=(",", ":")))
