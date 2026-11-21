"""Shared prepaid budget authority for Global AI (Staging + Production).

Reserve BEFORE every model call, settle AFTER it. All amounts are integer
micro-USD. Every failure fails closed (no model call). Reservations are never
returned after a provider request may have been sent: a settled reservation is
FINALIZED at observed usage (authoritative token counts returned by the
provider) or UNCERTAIN at its full amount. The only exception is ``release()``
for a request that provably never left the process (FINALIZED at zero).

This is an application-side estimate. It cannot guarantee zero overrun: the
provider does not expose a synchronous authoritative balance, prices may
change, and usage reporting can lag. Keep a safety reserve and the provider
project spend limit as independent controls.
"""
from __future__ import annotations

import logging
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timezone as dt_timezone

from django.conf import settings
from django.db import connections, transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from apps.ai_core.engine.budget import BudgetExceeded

LEDGER_ALIAS = "ai_ledger"
INPUT_OVERHEAD_TOKENS = 2000     # message framing + structured-output schema (conservative)
SAFETY_FACTOR_NUM, SAFETY_FACTOR_DEN = 5, 4   # x1.25 on the worst-case estimate
MAX_TOTAL_MICRO = 9_223_372_036_854_775_807  # PostgreSQL bigint bound; no fixed business spend cap
EXPECTED_SERVICES = {"staging": "srv-dbm7dvc9v7es7393g70g", "production": "srv-dadn07eq1p3s73eccau0"}
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DB_NAME = re.compile(r"[A-Za-z0-9_]{1,63}\Z")
_logger = logging.getLogger(__name__)


class LedgerUnavailable(BudgetExceeded):
    """Configuration, identity or database failure: no model call."""


class BudgetExhausted(BudgetExceeded):
    """Remaining allowance below the worst-case cost of this request."""


class EmergencyStop(BudgetExceeded):
    """Kill switch active (environment or ledger)."""


class StagingDailyCapReached(BudgetExhausted):
    """Independent STAGING daily ceiling (paid model calls or money) reached."""


@dataclass(frozen=True)
class StagingDailyLimit:
    """Per-UTC-day ceiling for STAGING model calls on the shared ledger.

    Enforced inside the same locked ledger transaction as the reservation, so
    concurrent requests (threads, workers, processes) can never exceed it.
    Counts every staging reservation of the day: FINALIZED at observed cost,
    RESERVED and UNCERTAIN at their full reserved amount (never optimistic).
    """
    max_requests: int
    cap_micro: int


def staging_daily_limit() -> StagingDailyLimit:
    """Read the staging ceiling; missing or invalid configuration fails closed."""
    max_requests = getattr(settings, "VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS", 0)
    cap_micro = getattr(settings, "VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD", 0)
    if (type(max_requests) is not int or type(cap_micro) is not int
            or not 1 <= max_requests <= 100_000 or not 1 <= cap_micro <= MAX_TOTAL_MICRO):
        raise LedgerUnavailable("staging daily ceiling not configured")
    return StagingDailyLimit(max_requests, cap_micro)


def _utc_day_start(now=None):
    now = (now or timezone.now()).astimezone(dt_timezone.utc)
    return datetime.combine(now.date(), dt_time.min, tzinfo=dt_timezone.utc)


def _staging_usage_today(account):
    """(count, committed_micro) of today's staging reservations for this account."""
    from apps.ai_ledger.models import BudgetReservation

    agg = (BudgetReservation.objects.using(LEDGER_ALIAS)
           .filter(account=account, environment="staging", created_at__gte=_utc_day_start())
           .aggregate(n=Count("pk"),
                      held=Sum("reserved_micro", filter=~Q(status=BudgetReservation.FINALIZED)),
                      spent=Sum("observed_micro", filter=Q(status=BudgetReservation.FINALIZED))))
    return agg["n"] or 0, (agg["held"] or 0) + (agg["spent"] or 0)


@dataclass(frozen=True)
class LedgerConfig:
    ledger_id: uuid.UUID
    expected_db_name: str


@dataclass(frozen=True)
class Reservation:
    id: uuid.UUID
    amount_micro: int
    input_price: int
    output_price: int


def ledger_enabled() -> bool:
    try:
        ledger_configuration()
        return True
    except LedgerUnavailable:
        return False


def ledger_configuration() -> LedgerConfig:
    if not getattr(settings, "VORNEQ_AI_LEDGER_ENABLED", False):
        raise LedgerUnavailable("shared ledger disabled")
    if LEDGER_ALIAS not in connections.databases:
        raise LedgerUnavailable("shared ledger alias missing")
    try:
        ledger_id = uuid.UUID(str(getattr(settings, "VORNEQ_AI_LEDGER_ID", "")))
    except ValueError as exc:
        raise LedgerUnavailable("invalid ledger id") from exc
    name = getattr(settings, "VORNEQ_AI_LEDGER_DB_NAME", "")
    if not isinstance(name, str) or not _DB_NAME.fullmatch(name):
        raise LedgerUnavailable("invalid ledger database name")
    return LedgerConfig(ledger_id, name)


def worst_case_cost_micro(*, input_bytes: int, max_output_tokens: int, input_price: int, output_price: int) -> int:
    """Upper bound: a BPE token covers >= 1 UTF-8 byte, so tokens <= bytes."""
    if min(input_bytes, max_output_tokens, input_price, output_price) < 0:
        raise LedgerUnavailable("invalid cost inputs")
    raw = (input_bytes + INPUT_OVERHEAD_TOKENS) * input_price + max_output_tokens * output_price
    base = math.ceil(raw / 1_000_000)
    return max(1, math.ceil(base * SAFETY_FACTOR_NUM / SAFETY_FACTOR_DEN))


def observed_cost_micro(input_tokens: int, output_tokens: int, input_price: int, output_price: int) -> int:
    return max(0, math.ceil((input_tokens * input_price + output_tokens * output_price) / 1_000_000))


def _verify_identity(expected_db_name: str):
    connection = connections[LEDGER_ALIAS]
    if connection.vendor != "postgresql":
        raise LedgerUnavailable("shared ledger requires PostgreSQL")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        actual = cursor.fetchone()[0]
    if actual != expected_db_name:
        raise LedgerUnavailable("shared ledger database identity mismatch")


def reserve(*, actor_id: int, model: str, input_bytes: int, max_output_tokens: int) -> Reservation:
    """Reserve for the CURRENT runtime (environment, Render service and SHA)."""
    import os
    if getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False):
        raise EmergencyStop("emergency stop (environment)")
    environment = getattr(settings, "VORNEQ_ENV", "")
    # Staging always carries its own daily ceiling, independent of the shared
    # allowance and of every request-quota or "unmetered" flag. Production is unchanged.
    staging_daily = staging_daily_limit() if environment == "staging" else None
    return reserve_with_config(
        ledger_configuration(), environment=environment,
        service_id=os.environ.get("RENDER_SERVICE_ID", ""),
        git_sha=os.environ.get("RENDER_GIT_COMMIT", ""), actor_id=actor_id, model=model,
        input_bytes=input_bytes, max_output_tokens=max_output_tokens, staging_daily=staging_daily)


_WORKER_SERVICE = re.compile(r"srv-[a-z0-9]{20,32}\Z")
# Same format as the paid-worker owner grant in image policy. Duplicated ON
# PURPOSE: the ledger re-validates independently of the caller (defense in
# depth) and never imports apps.ai_core.image_generation (no import cycle).
_PAID_WORKER_GRANT = re.compile(r"OWNER-AUTH-AI-IMAGE-PAID-WORKER-STAGING-[A-Z0-9-]{6,100}\Z")


def _image_worker_client(config: LedgerConfig, environment, service_id, git_sha) -> bool:
    """The ONLY non-web ledger client: the separate paid Staging image Worker.

    Re-validated here, independently of the image policy: staging runtime,
    paid-worker switch and owner grant, configured worker service ID equal to
    the running process identity, authorized SHA equal to both the running
    commit and the SHA recorded on the reservation, and the configured image
    account (never the chat account). The account itself must still be
    staging-only and not stopped (checked under lock in reserve_with_config).
    """
    import os
    worker_id = getattr(settings, "VORNEQ_AI_IMAGE_WORKER_SERVICE_ID", "")
    authorized_sha = getattr(settings, "VORNEQ_AI_IMAGE_AUTHORIZED_SHA", "")
    grant = getattr(settings, "VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH", "")
    if (environment != "staging"
            or getattr(settings, "VORNEQ_ENV", "") != "staging"
            or getattr(settings, "DEBUG", True) is not False
            or getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False)
            or getattr(settings, "VORNEQ_AI_IMAGE_ENABLED", False) is not True
            or getattr(settings, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", False) is not True
            or getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "") != "openai"
            or getattr(settings, "VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED", False) is not True
            or not isinstance(grant, str) or not _PAID_WORKER_GRANT.fullmatch(grant)
            or not isinstance(worker_id, str) or not _WORKER_SERVICE.fullmatch(worker_id)
            or worker_id in EXPECTED_SERVICES.values()
            or service_id != worker_id or os.environ.get("RENDER_SERVICE_ID") != worker_id
            or not isinstance(authorized_sha, str) or not _SHA.fullmatch(authorized_sha)
            or git_sha != authorized_sha or os.environ.get("RENDER_GIT_COMMIT") != authorized_sha):
        return False
    try:
        image_id = uuid.UUID(str(getattr(settings, "VORNEQ_AI_IMAGE_LEDGER_ID", "")))
        chat_id = uuid.UUID(str(getattr(settings, "VORNEQ_AI_LEDGER_ID", "")))
    except ValueError:
        return False
    return config.ledger_id == image_id and image_id != chat_id


def _approved_client(config: LedgerConfig, environment, service_id, git_sha) -> bool:
    if EXPECTED_SERVICES.get(environment) is not None and service_id == EXPECTED_SERVICES[environment]:
        return True
    return _image_worker_client(config, environment, service_id, git_sha)


def reservation_still_open(reservation: Reservation) -> bool:
    """Read-only re-check right before an irreversible provider call.

    True only if the reservation is still RESERVED and its account is not
    emergency-stopped. Any error is False (fail closed). Closes the window in
    which an owner stop between reserve and call would otherwise be ignored.
    """
    from apps.ai_ledger.models import BudgetReservation
    try:
        with transaction.atomic(using=LEDGER_ALIAS):
            row = (BudgetReservation.objects.using(LEDGER_ALIAS).select_related("account")
                   .get(id=reservation.id))
            return row.status == BudgetReservation.RESERVED and not row.account.emergency_stop
    except Exception:
        return False


def reserve_with_config(config: LedgerConfig, *, environment, service_id, git_sha, actor_id, model,
                        input_bytes, max_output_tokens, staging_daily=None) -> Reservation:
    from apps.ai_ledger.models import BudgetAccount, BudgetReservation

    if not _approved_client(config, environment, service_id, git_sha):
        raise LedgerUnavailable("runtime is not an approved ledger client")
    if not isinstance(git_sha, str) or not _SHA.fullmatch(git_sha):
        raise LedgerUnavailable("runtime SHA unavailable")
    if type(actor_id) is not int or actor_id <= 0 or not isinstance(model, str) or not model:
        raise LedgerUnavailable("invalid reservation request")
    if type(input_bytes) is not int or type(max_output_tokens) is not int:
        raise LedgerUnavailable("invalid reservation size")
    if staging_daily is not None and (environment != "staging"
                                      or not isinstance(staging_daily, StagingDailyLimit)):
        raise LedgerUnavailable("staging daily ceiling misapplied")
    try:
        with transaction.atomic(using=LEDGER_ALIAS):
            _verify_identity(config.expected_db_name)
            account = (BudgetAccount.objects.using(LEDGER_ALIAS).select_for_update()
                       .get(ledger_id=config.ledger_id))
            if account.emergency_stop:
                raise EmergencyStop("emergency stop (ledger)")
            if environment not in account.allowed_environments.split(","):
                raise LedgerUnavailable("environment not allowed by ledger")
            if service_id not in EXPECTED_SERVICES.values() and account.allowed_environments != "staging":
                raise LedgerUnavailable("worker client requires a staging-only account")
            if account.model_id != model:
                raise LedgerUnavailable("model not approved by ledger")
            if account.total_allowance_micro <= 0 or account.total_allowance_micro > MAX_TOTAL_MICRO:
                raise LedgerUnavailable("invalid ledger allowance")
            amount = worst_case_cost_micro(
                input_bytes=input_bytes, max_output_tokens=max_output_tokens,
                input_price=account.input_price_micro_per_mtok,
                output_price=account.output_price_micro_per_mtok)
            if account.remaining_micro() < amount:
                raise BudgetExhausted("shared prepaid allowance exhausted")
            if staging_daily is not None:
                # Same transaction, account row still locked: serialized with
                # every other reservation of this account.
                count, committed = _staging_usage_today(account)
                if count >= staging_daily.max_requests:
                    _logger.warning("ai_ledger_staging_daily_cap_reached kind=requests")
                    raise StagingDailyCapReached("staging daily request ceiling reached")
                if committed + amount > staging_daily.cap_micro:
                    _logger.warning("ai_ledger_staging_daily_cap_reached kind=amount")
                    raise StagingDailyCapReached("staging daily amount ceiling reached")
            BudgetAccount.objects.using(LEDGER_ALIAS).filter(pk=account.pk).update(
                reserved_micro=F("reserved_micro") + amount)
            reservation = BudgetReservation.objects.using(LEDGER_ALIAS).create(
                id=uuid.uuid4(), account=account, environment=environment, service_id=service_id,
                git_sha=git_sha, actor_id=actor_id, reserved_micro=amount)
    except BudgetExceeded:
        raise
    except Exception as exc:  # DatabaseError, DoesNotExist, programming errors: fail closed
        raise LedgerUnavailable("shared ledger unavailable") from exc
    return Reservation(reservation.id, amount, account.input_price_micro_per_mtok,
                       account.output_price_micro_per_mtok)


def settle(reservation: Reservation, *, usage=None, outcome: str) -> str | None:
    """Return the *committed* ledger state (finalized/uncertain), or None.

    The return value is an acknowledgement only after the transaction commits.
    A failed transaction or an already-settled reservation returns None; neither
    is an acknowledgement of this attempt. Existing text-chat callers may
    continue to ignore the result. Never raises: failed settlements retain the
    full RESERVED allowance for manual reconciliation.
    """
    from apps.ai_ledger.models import BudgetAccount, BudgetReservation

    valid_usage = (isinstance(usage, tuple) and len(usage) == 2
                   and all(type(v) is int and 0 <= v <= 10_000_000 for v in usage))
    try:
        with transaction.atomic(using=LEDGER_ALIAS):
            row = (BudgetReservation.objects.using(LEDGER_ALIAS).select_for_update()
                   .get(id=reservation.id))
            if row.status != BudgetReservation.RESERVED:
                return
            BudgetAccount.objects.using(LEDGER_ALIAS).select_for_update().get(pk=row.account_id)
            updates = {"reserved_micro": F("reserved_micro") - row.reserved_micro}
            if valid_usage:
                observed = observed_cost_micro(usage[0], usage[1], reservation.input_price,
                                               reservation.output_price)
                updates["finalized_micro"] = F("finalized_micro") + observed
                row.status, row.observed_micro = BudgetReservation.FINALIZED, observed
                row.input_tokens, row.output_tokens = usage
            else:
                updates["uncertain_micro"] = F("uncertain_micro") + row.reserved_micro
                row.status = BudgetReservation.UNCERTAIN
            BudgetAccount.objects.using(LEDGER_ALIAS).filter(pk=row.account_id).update(**updates)
            row.outcome = (outcome or "")[:40]
            row.settled_at = timezone.now()
            row.save(using=LEDGER_ALIAS)
        # Do not return from within atomic(): the DB commit must have succeeded.
        return row.status
    except Exception:
        _logger.warning("ai_ledger_settle_failed reservation=%s", reservation.id)
        return None


RELEASE_PREFIX = "released:"
RELEASED = "released"
_RELEASE_REASON = re.compile(r"[a-z0-9_]{1,30}\Z")


def release(reservation: Reservation, *, reason: str) -> str | None:
    """Return ``"released"`` only after commit, for a reservation whose paid
    provider request provably never left this process.

    Callers must NOT use this for timeouts, disconnects, HTTP 400/401/429/5xx
    or any outcome after the request was sent: without proof of no charge they
    stay UNCERTAIN (``settle(usage=None)``). No schema change: the reservation
    is closed as FINALIZED at zero observed cost with outcome
    ``released:<reason>`` (auditable). Atomic and idempotent: a reservation
    that is no longer RESERVED is never touched again (returns None).
    """
    from apps.ai_ledger.models import BudgetAccount, BudgetReservation

    if not isinstance(reason, str) or not _RELEASE_REASON.fullmatch(reason):
        _logger.warning("ai_ledger_release_rejected_reason reservation=%s", reservation.id)
        return None
    try:
        with transaction.atomic(using=LEDGER_ALIAS):
            row = (BudgetReservation.objects.using(LEDGER_ALIAS).select_for_update()
                   .get(id=reservation.id))
            if row.status != BudgetReservation.RESERVED:
                return None
            BudgetAccount.objects.using(LEDGER_ALIAS).select_for_update().get(pk=row.account_id)
            BudgetAccount.objects.using(LEDGER_ALIAS).filter(pk=row.account_id).update(
                reserved_micro=F("reserved_micro") - row.reserved_micro)
            row.status, row.observed_micro = BudgetReservation.FINALIZED, 0
            row.input_tokens, row.output_tokens = 0, 0
            row.outcome = (RELEASE_PREFIX + reason)[:40]
            row.settled_at = timezone.now()
            row.save(using=LEDGER_ALIAS)
        return RELEASED
    except Exception:
        _logger.warning("ai_ledger_release_failed reservation=%s", reservation.id)
        return None
