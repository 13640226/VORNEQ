"""One-use, Staging-only PAID image smoke test (OpenAI Images API, one job).

Default is a READ-ONLY preflight that prints every control and ends in NO_GO
unless all of them pass. Only ``--execute`` with a fresh, unedited GitHub owner
release, an armed one-off process and an unconsumed one-use receipt can make
exactly ONE paid request for ONE disposable user. The service's own image gates
stay CLOSED (opened only inside this process); no Worker is used or enabled.

Money controls, in order, all before the provider call:
  1. owner manifest caps the request (``max_cost_microusd`` <= 100000 = 0.10 USD)
     and states the OpenAI project spend limit (owner-attested, not verifiable here);
  2. the shared ledger reserves the WORST CASE (prompt bytes + overhead at the
     text price, ``VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND`` at the image price, x1.25)
     on a SEPARATE staging-only image account, inside the daily staging ceiling;
  3. a reservation above the per-request ceiling is released without any call.
The reservation is a defensible bound only if the provider bills <= the token
bound; that cannot be proven before the call, hence the independent provider
project limit is a required (attested) control. Ledger rows are never deleted.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.conf import settings

from apps.core import c02_owner_release as legacy
from apps.core import staging_image_0004_runner as runner0004
from apps.core import staging_image_mock_e2e as e2e

Refused, Aborted, require = e2e.Refused, e2e.Aborted, e2e.require

ISSUE = e2e.ISSUE
HEADER = "STAGING_IMAGE_PAID_SMOKE_OWNER_RELEASE_V1"
DECISION = "AUTHORIZE_STAGING_IMAGE_PAID_SMOKE_ONCE"
RISK = "ACCEPT_STAGING_PAID_IMAGE_SMOKE_COST_AND_SHARED_LEDGER_WRITE"
MODEL = "gpt-image-2.6-flare"
SIZE = "1024x1024"
QUALITY = "low"
COMPLEXITY = "low"
MAX_COST_CEILING_MICRO = 100_000          # 0.10 USD: hard ceiling for this smoke path
OUTPUT_BOUND_CEILING = 20_000
PROVIDER_BUDGET_MAX_USD = 20
ARM_MODE = e2e.ARM_MODE
ARM_MODE_KEY = "VORNEQ_IMAGE_PAID_SMOKE_WRITE_MODE"
ARM_SHA_KEY = "VORNEQ_IMAGE_PAID_SMOKE_ARMED_SHA"
AUTH_KEY = "VORNEQ_IMAGE_PAID_SMOKE_AUTH"
COMMENT_KEY = "VORNEQ_IMAGE_PAID_SMOKE_OWNER_COMMENT_ID"
TOKEN_KEY = e2e.TOKEN_KEY  # existing scoped read-only GitHub token, never logged
BACKUP_KEY = "VORNEQ_IMAGE_PAID_SMOKE_BACKUP_SHA256"
EVIDENCE_KEY = "VORNEQ_IMAGE_PAID_SMOKE_BACKUP_EVIDENCE"
RECEIPT_EVENT = "staging.ai_image_paid_smoke_one_use_release_consumed"
USER_PREFIX = "vorneq-paid-smoke-"
PROMPT = "A simple flat illustration of a small green leaf on a white background"
AUTH = re.compile(
    r"OWNER-AUTH-STAGING-AI-IMAGE-PAID-SMOKE-(?P<id>[A-Z0-9-]{8,60}) @ (?P<sha>[0-9a-f]{40})\Z"
)
FIELDS = frozenset({
    "decision", "release_id", "sha", "service_id", "postgres_id", "database",
    "provider", "paid_calls", "model", "size", "quality", "complexity", "max_jobs",
    "max_cost_microusd", "image_ledger_id", "ledger_shared_with_production_accepted",
    "openai_project_budget_usd", "bucket", "backup_sha256", "backup_evidence",
    "backup_exported_at", "restore_verified_at", "expires_at", "risk_acceptance",
})


@dataclass(frozen=True)
class ApprovedTarget:
    release_id: str
    proof: legacy.VerifiedOwnerRelease
    max_cost_micro: int
    image_ledger_id: uuid.UUID


# --- Owner release -----------------------------------------------------------

def validate_comment(comment, *, comment_id, expected_sha, release_id,
                     backup_sha256, backup_evidence, now=None):
    """Pure validation of a paid-smoke owner comment (same origin rules as E2E)."""
    deny = e2e._deny
    deny(isinstance(comment, dict), "invalid GitHub comment")
    deny(type(comment_id) is int and 0 < comment_id < 10**18, "bad comment ID")
    deny(isinstance(expected_sha, str) and e2e._SHA.fullmatch(expected_sha), "invalid SHA")
    deny(isinstance(release_id, str) and e2e._RELEASE.fullmatch(release_id), "bad release ID")
    deny(isinstance(backup_sha256, str) and e2e._DIGEST.fullmatch(backup_sha256),
         "missing backup digest")
    deny(isinstance(backup_evidence, str) and e2e._EVIDENCE.fullmatch(backup_evidence),
         "missing restore evidence reference")
    api = "https://api.github.com/repos/13640226/VORNEQ"
    web = "https://github.com/13640226/VORNEQ"
    deny(comment.get("id") == comment_id and type(comment.get("id")) is int,
         "comment ID mismatch")
    deny(comment.get("url") == f"{api}/issues/comments/{comment_id}"
         and comment.get("issue_url") == f"{api}/issues/{ISSUE}"
         and comment.get("html_url") == f"{web}/issues/{ISSUE}#issuecomment-{comment_id}",
         "wrong GitHub issue origin")
    user = comment.get("user")
    deny(isinstance(user, dict) and user.get("login") == "13640226"
         and user.get("id") == 199411505 and type(user.get("id")) is int
         and user.get("type") == "User" and comment.get("author_association") == "OWNER",
         "GitHub owner identity mismatch")
    try:
        created = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(comment["updated_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, AttributeError, ValueError):
        raise legacy.OwnerReleaseDenied("invalid GitHub timestamps") from None
    deny(created.tzinfo is not None and created.utcoffset() == timedelta(0)
         and created == updated, "edited or non-UTC grant")
    current = (now if now is not None else datetime.now(timezone.utc)).astimezone(timezone.utc)
    deny(created - timedelta(seconds=30) <= current <= created + e2e.MAX_AGE,
         "expired or future owner release")
    body = comment.get("body")
    deny(isinstance(body, str) and len(body) <= 4096, "invalid grant body")
    parts = body.strip().split("\n", 1)
    deny(len(parts) == 2 and parts[0] == HEADER, "wrong release header")
    try:
        manifest = json.loads(parts[1], object_pairs_hook=e2e._unique)
    except (ValueError, TypeError, Refused):
        raise legacy.OwnerReleaseDenied("invalid release JSON") from None
    deny(isinstance(manifest, dict) and set(manifest) == FIELDS, "release fields missing/extra")
    expected = {
        "decision": DECISION, "release_id": release_id, "sha": expected_sha,
        "service_id": e2e.SERVICE, "postgres_id": e2e.POSTGRES, "database": e2e.DATABASE,
        "provider": "openai", "paid_calls": True, "model": MODEL, "size": SIZE,
        "quality": QUALITY, "complexity": COMPLEXITY, "max_jobs": 1, "bucket": e2e.BUCKET,
        "ledger_shared_with_production_accepted": True,
        "backup_sha256": backup_sha256, "backup_evidence": backup_evidence,
        "risk_acceptance": RISK,
    }
    deny(all(manifest.get(k) == v and type(manifest.get(k)) is type(v)
             for k, v in expected.items()), "owner manifest scope mismatch")
    cost = manifest.get("max_cost_microusd")
    deny(type(cost) is int and 1 <= cost <= MAX_COST_CEILING_MICRO, "invalid cost ceiling")
    budget = manifest.get("openai_project_budget_usd")
    deny(type(budget) is int and 1 <= budget <= PROVIDER_BUDGET_MAX_USD,
         "provider project budget not attested")
    try:
        ledger_id = uuid.UUID(manifest.get("image_ledger_id"))
    except (ValueError, TypeError, AttributeError):
        raise legacy.OwnerReleaseDenied("invalid image ledger ID") from None
    exported = e2e._utc(manifest["backup_exported_at"], "invalid backup time")
    restored = e2e._utc(manifest["restore_verified_at"], "invalid restore time")
    deny(created - timedelta(hours=2) <= exported <= restored <= created,
         "backup is not fresh or restore time is invalid")
    deny(current - timedelta(hours=2) <= exported and restored <= current,
         "backup too old at point of use")
    expiry = e2e._utc(manifest["expires_at"], "invalid expiry")
    deny(created < expiry <= created + e2e.MAX_AGE and current < expiry,
         "release expired or excessive TTL")
    proof = legacy.VerifiedOwnerRelease(
        release_id=release_id, comment_id=comment_id, sha=expected_sha,
        body_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        backup_sha256=backup_sha256, backup_evidence=backup_evidence, expires_at=expiry,
    )
    return ApprovedTarget(release_id, proof, cost, ledger_id)


def verify_live(environ, *, expected_sha, release_id):
    raw_id = environ.get(COMMENT_KEY, "")
    e2e._deny(isinstance(raw_id, str) and re.fullmatch(r"[1-9][0-9]{0,17}", raw_id),
              "missing owner comment ID")
    token = environ.get(TOKEN_KEY, "")
    e2e._deny(isinstance(token, str) and bool(token.strip()), "GitHub read token missing")
    digest, evidence = environ.get(BACKUP_KEY, ""), environ.get(EVIDENCE_KEY, "")
    e2e._deny(isinstance(digest, str) and e2e._DIGEST.fullmatch(digest), "backup hash missing")
    e2e._deny(isinstance(evidence, str) and e2e._EVIDENCE.fullmatch(evidence),
              "restore evidence missing")
    comment_id = int(raw_id)
    return validate_comment(
        legacy.fetch_github_comment(comment_id, token), comment_id=comment_id,
        expected_sha=expected_sha, release_id=release_id,
        backup_sha256=digest, backup_evidence=evidence,
    )


# --- Cost model ----------------------------------------------------------------

def worst_case_micro(*, prompt=PROMPT, output_bound=None, prices=None):
    """Exactly the ledger's own reservation formula for this smoke request."""
    from apps.ai_core.image_generation.policy import OFFICIAL_PRICES_MICRO_PER_MTOK
    from apps.ai_ledger.service import worst_case_cost_micro
    bound = output_bound if output_bound is not None else getattr(
        settings, "VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND", 0)
    in_price, out_price = prices or OFFICIAL_PRICES_MICRO_PER_MTOK[MODEL]
    return worst_case_cost_micro(input_bytes=len(prompt.encode("utf-8")),
                                 max_output_tokens=bound, input_price=in_price,
                                 output_price=out_price)


def max_output_bound_for(cap_micro, *, prompt=PROMPT, prices=None):
    """Largest output-token bound whose worst-case reservation fits ``cap_micro``."""
    lo, hi = 0, OUTPUT_BOUND_CEILING
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if worst_case_micro(prompt=prompt, output_bound=mid, prices=prices) <= cap_micro:
            lo = mid
        else:
            hi = mid - 1
    return lo


# --- Read-only preflight ---------------------------------------------------------

class Checks:
    def __init__(self):
        self.items = []

    def add(self, name, ok, detail=""):
        self.items.append((name, bool(ok), detail))
        return bool(ok)

    @property
    def go(self):
        return bool(self.items) and all(ok for _, ok, _ in self.items)

    def lines(self):
        for name, ok, detail in self.items:
            yield "CHECK {} {}{}".format(name, "PASS" if ok else "FAIL",
                                         " " + detail if detail else "")


def _settings_checks(checks, *, cap_micro):
    from apps.ai_core.image_generation import policy
    from apps.ai_core.image_generation.providers import configured_complexity
    bound = getattr(settings, "VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND", 0)
    request_cap = policy.max_request_micro()
    daily = getattr(settings, "VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD", 0)
    checks.add("model_setting", getattr(settings, "VORNEQ_AI_IMAGE_MODEL", "") == MODEL)
    checks.add("complexity_low", configured_complexity() == COMPLEXITY)
    checks.add("official_price_reference", MODEL in policy.OFFICIAL_PRICES_MICRO_PER_MTOK)
    checks.add("output_token_bound", type(bound) is int and 1 <= bound <= OUTPUT_BOUND_CEILING,
               "bound={}".format(bound))
    checks.add("per_request_cap", request_cap is not None and request_cap <= cap_micro,
               "cap_micro={}".format(request_cap))
    checks.add("daily_cap", type(daily) is int and request_cap is not None
               and request_cap <= daily, "daily_micro={}".format(daily))
    ok_bound = type(bound) is int and 1 <= bound <= OUTPUT_BOUND_CEILING
    worst = worst_case_micro() if ok_bound else None
    checks.add("worst_case_within_cap",
               worst is not None and request_cap is not None and worst <= request_cap,
               "worst_case_micro={} max_bound_for_cap={}".format(
                   worst, max_output_bound_for(min(request_cap or 0, cap_micro))))
    checks.add("safety_identifier_key", policy.safety_key_ready())
    checks.add("openai_key_present", bool(os.environ.get("OPENAI_API_KEY")))
    checks.add("openai_sdk_installed", importlib.util.find_spec("openai") is not None)
    checks.add("no_worker_identity",
               not getattr(settings, "VORNEQ_AI_IMAGE_WORKER_SERVICE_ID", "")
               and not policy.worker_enabled())
    return worst


def ledger_checks(checks, *, cap_micro, expected_image_ledger_id=None):
    """READ-ONLY ledger inspection inside a READ ONLY transaction."""
    from django.db import connections, transaction
    from apps.ai_core.image_generation.policy import OFFICIAL_PRICES_MICRO_PER_MTOK
    from apps.ai_ledger.service import LEDGER_ALIAS, LedgerUnavailable, ledger_configuration
    try:
        config = ledger_configuration()
    except LedgerUnavailable:
        checks.add("ledger_enabled", False)
        return None
    checks.add("ledger_enabled", True)
    raw = getattr(settings, "VORNEQ_AI_IMAGE_LEDGER_ID", "")
    try:
        image_id = uuid.UUID(str(raw))
    except ValueError:
        checks.add("image_ledger_id_configured", False)
        return None
    checks.add("image_ledger_id_configured", True)
    checks.add("image_ledger_separate_from_chat", image_id != config.ledger_id)
    if expected_image_ledger_id is not None:
        checks.add("image_ledger_matches_release", image_id == expected_image_ledger_id)
    connection = connections[LEDGER_ALIAS]
    if not checks.add("ledger_postgresql", connection.vendor == "postgresql"):
        return None
    info = {}
    try:
        with transaction.atomic(using=LEDGER_ALIAS):
            with connection.cursor() as c:
                c.execute("SET TRANSACTION READ ONLY")
                c.execute("SELECT current_database(), current_setting('transaction_read_only')")
                info["db"], info["ro"] = c.fetchone()
                c.execute("SELECT to_regclass('public.ai_ledger_budgetaccount') IS NOT NULL, "
                          "to_regclass('public.ai_ledger_budgetreservation') IS NOT NULL")
                info["tables"] = all(c.fetchone())
                info["migrated"] = False
                if info["tables"]:
                    c.execute("SELECT count(*) FROM django_migrations "
                              "WHERE app = 'ai_ledger' AND name = '0001_initial'")
                    info["migrated"] = c.fetchone()[0] == 1
                    c.execute("SELECT id, model_id, allowed_environments, emergency_stop, "
                              "input_price_micro_per_mtok, output_price_micro_per_mtok, "
                              "total_allowance_micro - safety_reserve_micro - "
                              "consumed_before_micro - reserved_micro - finalized_micro - "
                              "uncertain_micro FROM ai_ledger_budgetaccount WHERE ledger_id = %s",
                              [str(image_id)])
                    info["account"] = c.fetchone()
                    c.execute("SELECT DISTINCT environment FROM ai_ledger_budgetreservation")
                    info["envs"] = sorted(r[0] for r in c.fetchall())
                    if info["account"]:
                        c.execute("SELECT count(*) FROM ai_ledger_budgetreservation "
                                  "WHERE account_id = %s AND status IN ('reserved','uncertain')",
                                  [info["account"][0]])
                        info["open"] = c.fetchone()[0]
    except Exception as exc:
        checks.add("ledger_readable", False, type(exc).__name__)
        return None
    checks.add("ledger_readable", info.get("ro") == "on", "read_only_txn={}".format(info.get("ro")))
    checks.add("ledger_identity", info.get("db") == config.expected_db_name)
    checks.add("ledger_tables", info.get("tables"))
    checks.add("ledger_migration_recorded", info.get("migrated"))
    account = info.get("account")
    if not checks.add("image_account_exists", account is not None):
        return info
    _pk, model_id, envs, stop, in_price, out_price, remaining = account
    checks.add("image_account_model", model_id == MODEL)
    checks.add("image_account_staging_only", envs == "staging", "allowed={}".format(envs))
    checks.add("image_account_not_stopped", stop is False)
    checks.add("image_account_official_prices",
               (in_price, out_price) == OFFICIAL_PRICES_MICRO_PER_MTOK[MODEL],
               "prices={}/{}".format(in_price, out_price))
    checks.add("image_account_balance", remaining is not None and remaining >= cap_micro,
               "remaining_micro={}".format(remaining))
    checks.add("image_account_no_open_reservations", info.get("open") == 0,
               "open={}".format(info.get("open")))
    info["shared_with_production"] = "production" in info.get("envs", [])
    return info


def preflight(connection, expected_sha, *, environ, out=print, cap_micro=MAX_COST_CEILING_MICRO,
              expected_image_ledger_id=None):
    from django.contrib.auth import get_user_model
    from apps.ai_core.image_generation import policy
    checks = Checks()
    e2e.base_context(environ, expected_sha, connection.settings_dict)  # raises Refused
    runner0004.check_identity(runner0004.snapshot(connection), False)
    history, _tables = runner0004.state(connection)
    checks.add("ai_core_migrations_0001_0004", history == runner0004.POST_HISTORY)
    checks.add("service_image_gates_closed",
               not policy.enabled() and not policy.paid_provider_enabled())
    checks.add("image_queue_empty", not any(e2e.queue_state().values()))
    users = get_user_model().objects
    checks.add("no_residue_users", not users.filter(username__startswith=USER_PREFIX).exists()
               and not users.filter(username__startswith=e2e.USER_PREFIX).exists())
    _settings_checks(checks, cap_micro=cap_micro)
    info = ledger_checks(checks, cap_micro=cap_micro,
                         expected_image_ledger_id=expected_image_ledger_id)
    for line in checks.lines():
        out(line)
    if info is not None and "envs" in info:
        out("LEDGER_ENVIRONMENTS_SEEN={}".format(",".join(info["envs"]) or "-"))
        out("LEDGER_SHARED_WITH_PRODUCTION={}".format(info["shared_with_production"]))
    out("OPENAI_PROJECT_SPEND_LIMIT=OWNER_ATTESTED_ONLY")
    out("STAGING_IMAGE_PAID_SMOKE_PREFLIGHT: {}".format("GO" if checks.go else "NO_GO"))
    return checks


# --- Read-only ledger audit (all accounts, no credentials) ------------------------

def ledger_audit(*, out=print):
    """READ-ONLY inventory of the shared ledger for owner decisions.

    Runs inside a READ ONLY transaction on the ``ai_ledger`` alias, prints only
    identity facts, schema conformity, account parameters and aggregates. Never
    prints URLs, credentials, full ledger IDs, actor IDs or prompts.
    """
    from django.apps import apps
    from django.db import connections, transaction
    from apps.ai_ledger.service import LEDGER_ALIAS

    def put(key, value):
        out("LEDGER_AUDIT {}={}".format(key, value))

    def setting_uuid(name):
        try:
            return uuid.UUID(str(getattr(settings, name, "")))
        except ValueError:
            return None

    chat, image = setting_uuid("VORNEQ_AI_LEDGER_ID"), setting_uuid("VORNEQ_AI_IMAGE_LEDGER_ID")
    expected = getattr(settings, "VORNEQ_AI_LEDGER_DB_NAME", "")
    cfg = connections.databases.get(LEDGER_ALIAS, {})
    put("ledger_url_set", bool(os.environ.get("VORNEQ_AI_LEDGER_DATABASE_URL")))
    put("ledger_enabled_setting", getattr(settings, "VORNEQ_AI_LEDGER_ENABLED", None))
    put("expected_db_name", expected or "-")
    put("chat_ledger_id_set", chat is not None)
    put("image_ledger_id_set", image is not None)
    put("image_equals_chat", chat is not None and chat == image)
    put("host_label", (cfg.get("HOST") or "-").split(".")[0])
    models = {m._meta.db_table: m for m in apps.get_app_config("ai_ledger").get_models()}
    with transaction.atomic(using=LEDGER_ALIAS):
        with connections[LEDGER_ALIAS].cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
            c.execute("SELECT current_database(), current_user, session_user, "
                      "current_setting('server_version'), pg_is_in_recovery(), "
                      "current_setting('transaction_read_only')")
            db, user, session_user, version, replica, read_only = c.fetchone()
            put("current_database", db)
            put("db_matches_expected", db == expected)
            put("current_user", user)
            put("session_user", session_user)
            put("server_version", version.split(" ")[0])
            put("in_recovery_replica", replica)
            put("transaction_read_only", read_only)
            for table in sorted(models) + ["django_migrations"]:
                c.execute("SELECT to_regclass(%s) IS NOT NULL", ["public." + table])
                present = c.fetchone()[0]
                put("table_" + table, present)
                if present and table in models:
                    c.execute("SELECT column_name FROM information_schema.columns "
                              "WHERE table_schema = 'public' AND table_name = %s", [table])
                    actual = {r[0] for r in c.fetchall()}
                    wanted = {f.column for f in models[table]._meta.concrete_fields}
                    put("columns_" + table, "MATCH" if actual == wanted else "DIFF")
            c.execute("SELECT name FROM django_migrations WHERE app = 'ai_ledger' ORDER BY name")
            put("ai_ledger_migrations", ",".join(r[0] for r in c.fetchall()) or "-")
            c.execute("SELECT id, ledger_id::text, model_id, allowed_environments, emergency_stop, "
                      "input_price_micro_per_mtok, output_price_micro_per_mtok, "
                      "total_allowance_micro, safety_reserve_micro, consumed_before_micro, "
                      "reserved_micro, finalized_micro, uncertain_micro "
                      "FROM ai_ledger_budgetaccount ORDER BY id")
            accounts = c.fetchall()
            put("account_count", len(accounts))
            for (pk, ledger, model, envs, stop, in_price, out_price, total, safety, before,
                 reserved, finalized, uncertain) in accounts:
                role = ("chat" if chat and ledger == str(chat)
                        else "image" if image and ledger == str(image) else "other")
                c.execute("SELECT status, count(*), coalesce(sum(reserved_micro), 0), "
                          "coalesce(sum(observed_micro), 0) FROM ai_ledger_budgetreservation "
                          "WHERE account_id = %s GROUP BY status ORDER BY status", [pk])
                by_status = {s: [n, int(r), int(o)] for s, n, r, o in c.fetchall()}
                c.execute("SELECT environment, count(*) FROM ai_ledger_budgetreservation "
                          "WHERE account_id = %s GROUP BY environment ORDER BY environment", [pk])
                by_env = dict(c.fetchall())
                put("account", json.dumps({
                    "role": role, "ledger_id_prefix": ledger[:8], "model_id": model,
                    "allowed_environments": envs, "emergency_stop": stop,
                    "input_price_micro_per_mtok": in_price, "output_price_micro_per_mtok": out_price,
                    "total_allowance_micro": total, "safety_reserve_micro": safety,
                    "remaining_micro": total - safety - before - reserved - finalized - uncertain,
                    "reserved_micro": reserved, "finalized_micro": finalized,
                    "uncertain_micro": uncertain, "reservations_by_status": by_status,
                    "reservations_by_environment": by_env,
                    "totals_match_rows": (
                        reserved == by_status.get("reserved", [0, 0, 0])[1]
                        and uncertain == by_status.get("uncertain", [0, 0, 0])[1]
                        and finalized == by_status.get("finalized", [0, 0, 0])[2]),
                }, sort_keys=True))
            c.execute("SELECT count(*) FROM ai_ledger_budgetreservation WHERE status = 'reserved' "
                      "AND created_at < now() - interval '15 minutes'")
            put("stale_open_reservations_over_15min", c.fetchone()[0])
    put("RESULT", "READ_ONLY_LEDGER_AUDIT_COMPLETE")


# --- Authorization and receipt ---------------------------------------------------------

def authorize(environ, expected_sha, db_config):
    e2e.base_context(environ, expected_sha, db_config)
    require(environ.get(ARM_MODE_KEY) == ARM_MODE and environ.get(ARM_SHA_KEY) == expected_sha,
            "separate paid smoke owner release arm closed")
    match = AUTH.fullmatch(environ.get(AUTH_KEY, ""))
    require(match is not None and match.group("sha") == expected_sha,
            "missing exact SHA-bound one-use owner authorization")
    try:
        target = verify_live(environ, expected_sha=expected_sha, release_id=match.group("id"))
    except legacy.OwnerReleaseDenied as exc:
        raise Refused("authenticated GitHub owner permit denied: " + str(exc)) from None
    require(target.proof.backup_sha256 == environ.get(BACKUP_KEY), "backup evidence changed")
    return target


def consume_one_use_receipt(connection, target, expected_sha):
    receipt_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://github.com/13640226/VORNEQ/issues/{ISSUE}/paid-smoke/{target.release_id}",
    )
    receipt = connection.copy(alias="staging_image_paid_smoke_receipt")
    try:
        receipt.ensure_connection()
        require(receipt.get_autocommit(), "receipt session not in autocommit", Refused)
        runner0004.check_identity(runner0004.snapshot(receipt), False, Refused)
        with receipt.cursor() as c:
            c.execute(
                """
                INSERT INTO audit_auditevent
                    (event_id, schema_version, event_name, actor, target, outcome,
                     reason_code, correlation_id, metadata, retention_class, timestamp)
                VALUES (%s, 1, %s, %s::jsonb, %s::jsonb, 'granted',
                        'STG_IMAGE_PAID_SMOKE_RECEIPT', %s, %s::jsonb, 'security', now())
                ON CONFLICT (event_id) DO NOTHING RETURNING event_id
                """,
                [receipt_id, RECEIPT_EVENT,
                 json.dumps({"kind": "github_owner", "comment_id": target.proof.comment_id}),
                 json.dumps({"service": e2e.SERVICE, "database": e2e.DATABASE,
                             "model": MODEL, "max_cost_microusd": target.max_cost_micro}),
                 str(receipt_id),
                 json.dumps({"release_id": target.release_id, "sha": expected_sha,
                             "backup_sha256": target.proof.backup_sha256,
                             "owner_body_sha256": target.proof.body_sha256})],
            )
            require(c.fetchone() is not None, "one-use release already consumed", Refused)
    except Refused:
        raise
    except Exception as exc:
        raise Aborted("one-use receipt ambiguous/unavailable: " + type(exc).__name__) from None
    finally:
        receipt.close()


# --- One-use execution ---------------------------------------------------------------

def _gate_settings(target, expected_sha, user_id):
    return {
        "VORNEQ_AI_IMAGE_ENABLED": True,
        "VORNEQ_AI_IMAGE_PROVIDER": "openai",
        "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": True,
        "VORNEQ_AI_IMAGE_MODEL": MODEL,
        "VORNEQ_AI_IMAGE_COMPLEXITY": COMPLEXITY,
        "VORNEQ_AI_IMAGE_AUTHORIZED_SHA": expected_sha,
        "VORNEQ_AI_IMAGE_OWNER_AUTH": "OWNER-AUTH-AI-IMAGE-STAGING-" + target.release_id,
        "VORNEQ_AI_IMAGE_ALLOWED_USER_IDS": str(user_id),
        "VORNEQ_AI_IMAGE_WORKER_SERVICE_ID": "",
        "VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS": 1,
        "VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS": 1,
        "VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD": min(
            target.max_cost_micro,
            getattr(settings, "VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD", 0) or 0),
    }


def _reservation_line(reservation_id):
    from apps.ai_ledger.models import BudgetReservation
    from apps.ai_ledger.service import LEDGER_ALIAS
    row = (BudgetReservation.objects.using(LEDGER_ALIAS).filter(pk=reservation_id).first()
           if reservation_id else None)
    if row is None:
        return None, "PAID_SMOKE_LEDGER reservation=-"
    return row, ("PAID_SMOKE_LEDGER status={} outcome={} reserved_micro={} observed_micro={} "
                 "input_tokens={} output_tokens={}").format(
        row.status, row.outcome or "-", row.reserved_micro, row.observed_micro,
        row.input_tokens, row.output_tokens)


def execute_once(connection, target, expected_sha, *, public_host, out=print,
                 fetch=e2e.fetch_url, consume=consume_one_use_receipt, endpoint_host=None):
    endpoint_host = endpoint_host or e2e.configured_endpoint_host()
    require(bool(endpoint_host), "private R2 endpoint host unavailable")
    held = e2e.acquire_run_lock(connection)  # same lock as the mock E2E: one image op at a time
    try:
        return _execute_locked(connection, target, expected_sha, public_host=public_host,
                               out=out, fetch=fetch, consume=consume,
                               endpoint_host=endpoint_host)
    finally:
        e2e.release_run_lock(connection, held)


def _execute_locked(connection, target, expected_sha, *, public_host, out, fetch, consume,
                    endpoint_host):
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.test.utils import override_settings
    from django.urls import reverse
    from apps.ai_core.image_generation import policy
    from apps.ai_core.image_generation.service import process_next_image_job
    from apps.ai_core.models import AIImageDailyQuota, AIImageJob

    User = get_user_model()
    require(not any(e2e.queue_state().values()), "image queue is not empty")
    require(not User.objects.filter(username__startswith=USER_PREFIX).exists(),
            "residue of an earlier paid smoke run exists")
    day = datetime.now(timezone.utc).date()
    quota_before = AIImageDailyQuota.objects.filter(day_utc=day).first()
    quota_before = None if quota_before is None else quota_before.submitted
    consume(connection, target, expected_sha)
    out("PAID_SMOKE_ONE_USE_RECEIPT_CONSUMED release={}".format(target.release_id))

    report, users, key, clients = e2e.Report(), [], "", []
    outcome, failure = "not_started", None
    try:
        user = User(username="{}{}".format(USER_PREFIX, uuid.uuid4().hex[:12]), is_active=True)
        user.set_unusable_password()
        user.save()
        users.append(user)
        with override_settings(**_gate_settings(target, expected_sha, user.pk)):
            require(policy.enabled() and policy.paid_provider_enabled()
                    and not policy.worker_enabled(), "paid process gate state invalid", Aborted)
            report.ok("process_gate_paid_single_user", out)
            rid = uuid.uuid4()
            key = "ai-generated/{}/{}.png".format(user.pk, rid.hex)
            client = Client(HTTP_HOST=public_host)
            client.force_login(user)
            clients.append(client)
            r = client.post(reverse("ai_core:image-jobs"),
                            json.dumps({"request_id": str(rid), "prompt": PROMPT, "size": SIZE}),
                            content_type="application/json", secure=True)
            require(r.status_code == 202 and r.json().get("model") == MODEL,
                    "paid submit response invalid", Aborted)
            report.ok("api_submit_202", out)
            queued = list(AIImageJob.objects.filter(status=AIImageJob.STATUS_QUEUED)
                          .values_list("pk", flat=True))
            require(queued == [rid], "unrelated job in queue; provider not called", Aborted)
            require(process_next_image_job() == rid, "worker did not process the job", Aborted)
            job = AIImageJob.objects.get(pk=rid)
            row, line = _reservation_line(job.reservation_id)
            out("PAID_SMOKE_JOB status={} error_code={} attempts={}".format(
                job.status, job.error_code or "-", job.attempts))
            out(line)
            outcome = job.status
            require(job.status == AIImageJob.STATUS_COMPLETED and not job.is_mock
                    and job.storage_key == key and job.attempts == 1,
                    "paid job not completed: " + (job.error_code or job.status), Aborted)
            require(row is not None and row.status == "finalized"
                    and row.observed_micro is not None
                    and row.observed_micro <= target.max_cost_micro,
                    "ledger not finalized within cost ceiling", Aborted)
            report.ok("ledger_finalized_within_cap", out)
            r = client.get(reverse("ai_core:image-job-detail", args=[rid]), secure=True)
            body = r.json()
            require(r.status_code == 200 and body.get("status") == "completed"
                    and body.get("mock") is False and body.get("image_url"),
                    "owner detail invalid", Aborted)
            signed = body["image_url"]
            e2e.check_signed_url(signed, endpoint_host=endpoint_host)
            e2e.verify_signed_download(fetch(signed), job.image_digest)
            report.ok("signed_download_digest_match", out)
            unsigned = fetch(signed.split("?", 1)[0])
            require(isinstance(unsigned, e2e.Download) and unsigned.status in (400, 401, 403),
                    "object readable without signature", Aborted)
            report.ok("unsigned_access_denied", out)
    except Exception as exc:
        failure = exc
    finally:
        if outcome in (AIImageJob.STATUS_UNCERTAIN, AIImageJob.STATUS_RUNNING):
            # Possibly billed: keep job, user and object for manual reconciliation.
            for client in clients:
                try:
                    client.logout()
                except Exception:
                    pass
            out("PAID_SMOKE_CLEANUP DEFERRED_FOR_RECONCILIATION")
            failure = failure or Aborted("paid outcome uncertain")
        else:
            failure = e2e._cleanup(report, users, key, clients, day, quota_before, out) or failure
    if failure is not None:
        raise Aborted(str(failure) if isinstance(failure, (Refused, Aborted))
                      else "unexpected paid smoke failure: " + type(failure).__name__)
    return report
