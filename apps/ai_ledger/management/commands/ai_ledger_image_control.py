"""Inspect, stop or resume ONLY the separate staging image budget account.

  ai_ledger_image_control status --ledger-id UUID
  ai_ledger_image_control stop   --ledger-id UUID --confirm-ledger-id UUID
  ai_ledger_image_control resume --ledger-id UUID --confirm-ledger-id UUID

Never calls OpenAI. ``status`` runs in a READ ONLY transaction. ``stop`` and
``resume`` change exactly one column (``emergency_stop``) of exactly one row,
inside one transaction after the ledger database identity check, and only if:

* the id equals ``VORNEQ_AI_IMAGE_LEDGER_ID`` and differs from the chat
  ``VORNEQ_AI_LEDGER_ID`` (the chat account can never be selected here);
* the account is staging-only, uses the image model and the official prices.

``resume`` additionally refuses while the account has open (reserved) or
uncertain amounts: those must be reconciled by the owner first.
Stopping is always allowed for a matching account. ``stop`` and ``resume`` write
to the shared ledger and need the owner's explicit authorization.
"""
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from apps.ai_ledger.management.commands.ai_ledger_image_provision import (
    ALLOWED_ENVIRONMENTS,
    IMAGE_MODEL,
)
from apps.ai_ledger.service import (
    LEDGER_ALIAS,
    LedgerUnavailable,
    _verify_identity,
    ledger_configuration,
)

FIELDS = ("emergency_stop", "allowed_environments", "model_id", "total_allowance_micro",
          "safety_reserve_micro", "reserved_micro", "finalized_micro", "uncertain_micro")


def image_ledger_id(value):
    try:
        given = uuid.UUID(str(value or ""))
        configured = uuid.UUID(str(getattr(settings, "VORNEQ_AI_IMAGE_LEDGER_ID", "") or ""))
    except ValueError as exc:
        raise CommandError("ledger id is not a valid UUID") from exc
    if given != configured:
        raise CommandError("--ledger-id must equal the configured VORNEQ_AI_IMAGE_LEDGER_ID")
    return given


def account_problems(account):
    from apps.ai_core.image_generation.policy import OFFICIAL_PRICES_MICRO_PER_MTOK
    problems = []
    if account.allowed_environments != ALLOWED_ENVIRONMENTS:
        problems.append("account is not staging-only")
    if account.model_id != IMAGE_MODEL:
        problems.append("account model is not the image model")
    if (account.input_price_micro_per_mtok, account.output_price_micro_per_mtok) != \
            OFFICIAL_PRICES_MICRO_PER_MTOK.get(IMAGE_MODEL):
        problems.append("account prices differ from the official price reference")
    return problems


class Command(BaseCommand):
    help = "Status, stop or resume of the separate staging-only image budget account."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["status", "stop", "resume"])
        parser.add_argument("--ledger-id", required=True)
        parser.add_argument("--confirm-ledger-id")

    def handle(self, *args, **opts):
        action = opts["action"]
        image_id = image_ledger_id(opts["ledger_id"])
        if action != "status" and opts.get("confirm_ledger_id") != str(image_id):
            raise CommandError("--confirm-ledger-id must equal --ledger-id")
        try:
            config = ledger_configuration()
        except LedgerUnavailable as exc:
            raise CommandError(f"ledger not configured: {exc}") from exc
        if config.ledger_id == image_id:
            raise CommandError("image ledger id must differ from the chat ledger id")
        from apps.ai_ledger.models import BudgetAccount
        with transaction.atomic(using=LEDGER_ALIAS):
            try:
                _verify_identity(config.expected_db_name)
            except LedgerUnavailable as exc:
                raise CommandError(str(exc)) from exc
            accounts = BudgetAccount.objects.using(LEDGER_ALIAS)
            if action == "status":
                with connections[LEDGER_ALIAS].cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SHOW transaction_read_only")
                    self.stdout.write(f"read_only_txn={cursor.fetchone()[0]}")
                account = accounts.filter(ledger_id=image_id).first()
            else:
                account = accounts.select_for_update().filter(ledger_id=image_id).first()
            if account is None:
                raise CommandError("image ledger account does not exist; nothing changed")
            problems = account_problems(account)
            if action != "status":
                if problems:
                    raise CommandError("refused, nothing changed: " + "; ".join(problems))
                if action == "resume" and (account.reserved_micro or account.uncertain_micro):
                    raise CommandError("refused, nothing changed: open or uncertain amounts must be "
                                       "reconciled before resume")
                updated = accounts.filter(pk=account.pk, ledger_id=image_id).update(
                    emergency_stop=(action == "stop"))
                if updated != 1:
                    raise CommandError("expected exactly one image account row")
                account.refresh_from_db(using=LEDGER_ALIAS)
        self.stdout.write(f"ledger_id_prefix={str(image_id)[:8]}")
        for field in FIELDS:
            self.stdout.write(f"{field}={getattr(account, field)}")
        self.stdout.write(f"remaining_micro={account.remaining_micro()}")
        self.stdout.write("problems=" + (";".join(problems) or "none"))
        self.stdout.write("RESULT=" + {"status": "READ_ONLY_STATUS", "stop": "IMAGE_ACCOUNT_STOPPED",
                                       "resume": "IMAGE_ACCOUNT_RESUMED"}[action])
