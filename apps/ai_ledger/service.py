"""Shared prepaid budget authority for Global AI (Staging + Production).

Reserve BEFORE every model call, settle AFTER it. All amounts are integer
micro-USD. Every failure fails closed (no model call). Reservations are never
returned: a settled reservation is FINALIZED at observed usage (authoritative
token counts returned by the provider) or UNCERTAIN at its full amount.

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

from django.conf import settings
from django.db import connections, transaction
from django.db.models import F
from django.utils import timezone

from apps.ai_core.engine.budget import BudgetExceeded

LEDGER_ALIAS = "ai_ledger"
INPUT_OVERHEAD_TOKENS = 2000     # message framing + structured-output schema (conservative)
SAFETY_FACTOR_NUM, SAFETY_FACTOR_DEN = 5, 4   # x1.25 on the worst-case estimate
MAX_TOTAL_MICRO = 100_000_000    # 100 USD: refuse obviously wrong provisioning
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
    return reserve_with_config(
        ledger_configuration(), environment=environment,
        service_id=os.environ.get("RENDER_SERVICE_ID", ""),
        git_sha=os.environ.get("RENDER_GIT_COMMIT", ""), actor_id=actor_id, model=model,
        input_bytes=input_bytes, max_output_tokens=max_output_tokens)


def reserve_with_config(config: LedgerConfig, *, environment, service_id, git_sha, actor_id, model,
                        input_bytes, max_output_tokens) -> Reservation:
    from apps.ai_ledger.models import BudgetAccount, BudgetReservation

    if EXPECTED_SERVICES.get(environment) is None or service_id != EXPECTED_SERVICES[environment]:
        raise LedgerUnavailable("runtime is not an approved ledger client")
    if not isinstance(git_sha, str) or not _SHA.fullmatch(git_sha):
        raise LedgerUnavailable("runtime SHA unavailable")
    if type(actor_id) is not int or actor_id <= 0 or not isinstance(model, str) or not model:
        raise LedgerUnavailable("invalid reservation request")
    if type(input_bytes) is not int or type(max_output_tokens) is not int:
        raise LedgerUnavailable("invalid reservation size")
    try:
        with transaction.atomic(using=LEDGER_ALIAS):
            _verify_identity(config.expected_db_name)
            account = (BudgetAccount.objects.using(LEDGER_ALIAS).select_for_update()
                       .get(ledger_id=config.ledger_id))
            if account.emergency_stop:
                raise EmergencyStop("emergency stop (ledger)")
            if environment not in account.allowed_environments.split(","):
                raise LedgerUnavailable("environment not allowed by ledger")
            if account.model_id != model:
                raise LedgerUnavailable("model not approved by ledger")
            if account.total_allowance_micro > MAX_TOTAL_MICRO:
                raise LedgerUnavailable("ledger allowance outside sanity bound")
            amount = worst_case_cost_micro(
                input_bytes=input_bytes, max_output_tokens=max_output_tokens,
                input_price=account.input_price_micro_per_mtok,
                output_price=account.output_price_micro_per_mtok)
            if account.remaining_micro() < amount:
                raise BudgetExhausted("shared prepaid allowance exhausted")
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


def settle(reservation: Reservation, *, usage=None, outcome: str) -> None:
    """Finalize at observed usage, or mark UNCERTAIN at the full reserved amount.

    Never raises to the caller: if settlement fails, the reservation remains
    RESERVED and keeps counting against the allowance (safe direction).
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
    except Exception:
        _logger.warning("ai_ledger_settle_failed reservation=%s", reservation.id)
