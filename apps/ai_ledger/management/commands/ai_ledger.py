"""Operate the shared prepaid AI ledger. Never calls the provider or billing APIs.

  ai_ledger status
  ai_ledger provision --ledger-id UUID --total-usd 8.00 --safety-usd 2.00 \
      --consumed-before-usd 0 --model MODEL --input-usd-per-mtok X --output-usd-per-mtok Y \
      --confirm-ledger-id UUID
  ai_ledger stop | resume --confirm-ledger-id UUID
  ai_ledger record-external --usd 0.42 --note "billing console 2026-11-20" --confirm-ledger-id UUID

Values are USD (the ledger currency). EUR-denominated credit must be converted
by the owner with a documented rate and margin BEFORE provisioning.
Every write runs in one transaction on the ``ai_ledger`` alias after the
database identity check.
"""
import uuid
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from apps.ai_ledger.service import LEDGER_ALIAS, LedgerUnavailable, _verify_identity, ledger_configuration


def _micro(value, rounding):
    try:
        amount = (Decimal(value) * 1_000_000).to_integral_value(rounding=rounding)
    except (InvalidOperation, TypeError) as exc:
        raise CommandError("invalid amount") from exc
    if amount < 0:
        raise CommandError("negative amount")
    return int(amount)


class Command(BaseCommand):
    help = "Inspect or administer the shared prepaid AI budget ledger."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["status", "provision", "stop", "resume", "record-external"])
        parser.add_argument("--ledger-id")
        parser.add_argument("--confirm-ledger-id")
        parser.add_argument("--total-usd")
        parser.add_argument("--safety-usd", default="0")
        parser.add_argument("--consumed-before-usd", default="0")
        parser.add_argument("--model")
        parser.add_argument("--input-usd-per-mtok")
        parser.add_argument("--output-usd-per-mtok")
        parser.add_argument("--usd")
        parser.add_argument("--note", default="")

    def handle(self, *args, **opts):
        from apps.ai_ledger.models import BudgetAccount, ExternalUsageRecord
        try:
            config = ledger_configuration()
        except LedgerUnavailable as exc:
            raise CommandError(f"ledger not configured: {exc}") from exc
        action = opts["action"]
        if action != "status" and opts.get("confirm_ledger_id") != str(config.ledger_id):
            raise CommandError("--confirm-ledger-id must equal the configured VORNEQ_AI_LEDGER_ID")
        with transaction.atomic(using=LEDGER_ALIAS):
            _verify_identity(config.expected_db_name)
            accounts = BudgetAccount.objects.using(LEDGER_ALIAS)
            if action == "provision":
                if accounts.filter(ledger_id=config.ledger_id).exists():
                    raise CommandError("ledger account already provisioned")
                if opts.get("ledger_id") != str(config.ledger_id):
                    raise CommandError("--ledger-id must equal the configured VORNEQ_AI_LEDGER_ID")
                accounts.create(
                    ledger_id=config.ledger_id,
                    total_allowance_micro=_micro(opts["total_usd"], ROUND_FLOOR),
                    safety_reserve_micro=_micro(opts["safety_usd"], ROUND_CEILING),
                    consumed_before_micro=_micro(opts["consumed_before_usd"], ROUND_CEILING),
                    model_id=opts["model"] or "",
                    input_price_micro_per_mtok=_micro(opts["input_usd_per_mtok"], ROUND_CEILING),
                    output_price_micro_per_mtok=_micro(opts["output_usd_per_mtok"], ROUND_CEILING),
                )
            account = accounts.select_for_update().get(ledger_id=config.ledger_id)
            if action in ("stop", "resume"):
                accounts.filter(pk=account.pk).update(emergency_stop=(action == "stop"))
            elif action == "record-external":
                amount = _micro(opts["usd"], ROUND_CEILING)
                if amount <= 0 or not opts["note"]:
                    raise CommandError("record-external requires --usd > 0 and --note")
                ExternalUsageRecord.objects.using(LEDGER_ALIAS).create(
                    account=account, amount_micro=amount, note=opts["note"][:200])
                accounts.filter(pk=account.pk).update(consumed_before_micro=F("consumed_before_micro") + amount)
            account.refresh_from_db(using=LEDGER_ALIAS)
        fields = ("total_allowance_micro", "safety_reserve_micro", "consumed_before_micro", "reserved_micro",
                  "finalized_micro", "uncertain_micro", "emergency_stop", "model_id", "allowed_environments")
        for field in fields:
            self.stdout.write(f"{field}={getattr(account, field)}")
        self.stdout.write(f"remaining_micro={account.remaining_micro()}")
