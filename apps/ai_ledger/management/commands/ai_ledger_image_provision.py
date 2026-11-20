"""Provision the SEPARATE, staging-only image budget account. Never calls OpenAI.

  ai_ledger_image_provision --ledger-id UUID --total-usd 2.00 --safety-usd 0.50
  ai_ledger_image_provision ... --confirm-ledger-id UUID --execute

Default is a DRY RUN: it prints the plan and touches no database. With
``--execute`` it writes exactly one row on the ``ai_ledger`` alias after the
database identity check, and only if every guard holds:

* the id equals ``VORNEQ_AI_IMAGE_LEDGER_ID`` and differs from the chat
  ``VORNEQ_AI_LEDGER_ID`` (the chat account is never touched);
* model and prices come from the code table of official prices, not from flags;
* ``allowed_environments`` is forced to ``staging``;
* ``emergency_stop`` starts TRUE; opening it is a separate owner decision;
* total allowance is capped at ``MAX_TOTAL_USD`` and must leave room for at
  least one maximum-cost request above the safety reserve;
* an existing account with that id is never modified.

Executing this command writes to the shared ledger and needs the owner's
explicit authorization.
"""
import uuid
from decimal import ROUND_CEILING, ROUND_FLOOR

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.ai_ledger.management.commands.ai_ledger import _micro
from apps.ai_ledger.service import (
    LEDGER_ALIAS,
    LedgerUnavailable,
    _verify_identity,
    ledger_configuration,
)

IMAGE_MODEL = "gpt-image-2.6-flare"
ALLOWED_ENVIRONMENTS = "staging"
MAX_TOTAL_USD = 5
MAX_TOTAL_MICRO = MAX_TOTAL_USD * 1_000_000


def _uuid(value, name):
    try:
        return uuid.UUID(str(value or ""))
    except ValueError as exc:
        raise CommandError(f"{name} is not a valid UUID") from exc


def build_plan(*, ledger_id, total_usd, safety_usd):
    from apps.ai_core.image_generation.policy import (
        MAX_REQUEST_CEILING_MICRO,
        OFFICIAL_PRICES_MICRO_PER_MTOK,
    )
    image_id = _uuid(ledger_id, "--ledger-id")
    configured = _uuid(getattr(settings, "VORNEQ_AI_IMAGE_LEDGER_ID", ""), "VORNEQ_AI_IMAGE_LEDGER_ID")
    if image_id != configured:
        raise CommandError("--ledger-id must equal the configured VORNEQ_AI_IMAGE_LEDGER_ID")
    chat_id = str(getattr(settings, "VORNEQ_AI_LEDGER_ID", "") or "")
    if chat_id and chat_id.lower() == str(image_id):
        raise CommandError("image ledger id must differ from the chat VORNEQ_AI_LEDGER_ID")
    if IMAGE_MODEL not in OFFICIAL_PRICES_MICRO_PER_MTOK:
        raise CommandError("no official price reference for the image model")
    total = _micro(total_usd, ROUND_FLOOR)
    safety = _micro(safety_usd, ROUND_CEILING)
    if not 0 < total <= MAX_TOTAL_MICRO:
        raise CommandError(f"--total-usd must be > 0 and <= {MAX_TOTAL_USD}")
    max_request = int(getattr(settings, "VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD", 0) or 0)
    if not 0 < max_request <= MAX_REQUEST_CEILING_MICRO:
        raise CommandError("VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD must be set within the code ceiling")
    if total - safety < max_request:
        raise CommandError("allowance minus safety reserve must cover one maximum-cost request")
    in_price, out_price = OFFICIAL_PRICES_MICRO_PER_MTOK[IMAGE_MODEL]
    return {
        "ledger_id": image_id, "total_allowance_micro": total, "safety_reserve_micro": safety,
        "consumed_before_micro": 0, "model_id": IMAGE_MODEL,
        "input_price_micro_per_mtok": in_price, "output_price_micro_per_mtok": out_price,
        "allowed_environments": ALLOWED_ENVIRONMENTS, "emergency_stop": True,
    }


class Command(BaseCommand):
    help = "Plan (default) or create the separate staging-only image budget account."

    def add_arguments(self, parser):
        parser.add_argument("--ledger-id", required=True)
        parser.add_argument("--total-usd", required=True)
        parser.add_argument("--safety-usd", required=True)
        parser.add_argument("--confirm-ledger-id")
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **opts):
        plan = build_plan(ledger_id=opts["ledger_id"], total_usd=opts["total_usd"],
                          safety_usd=opts["safety_usd"])
        for key in sorted(plan):
            value = str(plan[key])[:8] + "…" if key == "ledger_id" else plan[key]
            self.stdout.write(f"PLAN {key}={value}")
        if not opts["execute"]:
            self.stdout.write("RESULT=DRY_RUN_NO_DATABASE_ACCESS")
            return
        if opts.get("confirm_ledger_id") != str(plan["ledger_id"]):
            raise CommandError("--execute requires --confirm-ledger-id equal to --ledger-id")
        try:
            config = ledger_configuration()
        except LedgerUnavailable as exc:
            raise CommandError(f"ledger not configured: {exc}") from exc
        if config.ledger_id == plan["ledger_id"]:
            raise CommandError("image ledger id must differ from the chat ledger id")
        from apps.ai_ledger.models import BudgetAccount
        with transaction.atomic(using=LEDGER_ALIAS):
            try:
                _verify_identity(config.expected_db_name)
            except LedgerUnavailable as exc:
                raise CommandError(str(exc)) from exc
            accounts = BudgetAccount.objects.using(LEDGER_ALIAS)
            if accounts.filter(ledger_id=plan["ledger_id"]).exists():
                raise CommandError("image ledger account already exists; nothing changed")
            account = accounts.create(**plan)
        self.stdout.write(f"remaining_micro={account.remaining_micro()}")
        self.stdout.write("RESULT=IMAGE_ACCOUNT_CREATED_EMERGENCY_STOP_ON")
