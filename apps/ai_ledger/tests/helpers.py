"""Shared SYNTHETIC fixtures for ledger tests (no network, no provider)."""
import os
import uuid

from django.db import connections

from apps.ai_ledger.models import BudgetAccount
from apps.ai_ledger.service import EXPECTED_SERVICES, LEDGER_ALIAS, worst_case_cost_micro

LEDGER_ID = uuid.UUID("11111111-2222-4333-8444-555555555555")
OTHER_LEDGER_ID = uuid.UUID("99999999-2222-4333-8444-555555555555")
MODEL = "synthetic-model"
SHA = "a" * 40
IN_PRICE, OUT_PRICE = 1_000_000, 4_000_000           # synthetic: $1 / $4 per 1M tokens
INPUT_BYTES, MAX_OUT = 1000, 1024
COST = worst_case_cost_micro(input_bytes=INPUT_BYTES, max_output_tokens=MAX_OUT,
                             input_price=IN_PRICE, output_price=OUT_PRICE)
SAFETY = 50_000


def ledger_settings():
    return {
        "VORNEQ_AI_LEDGER_ENABLED": True,
        "VORNEQ_AI_LEDGER_ID": str(LEDGER_ID),
        "VORNEQ_AI_LEDGER_DB_NAME": connections[LEDGER_ALIAS].settings_dict["NAME"],
    }


def provision(affordable, *, extra=0, **fields):
    total = SAFETY + affordable * COST + extra
    return BudgetAccount.objects.using(LEDGER_ALIAS).create(
        ledger_id=fields.pop("ledger_id", LEDGER_ID), total_allowance_micro=total,
        safety_reserve_micro=SAFETY, model_id=MODEL, input_price_micro_per_mtok=IN_PRICE,
        output_price_micro_per_mtok=OUT_PRICE, **fields)


def runtime(environment="production"):
    return {"RENDER_SERVICE_ID": EXPECTED_SERVICES[environment], "RENDER_GIT_COMMIT": SHA}


def env_without_render():
    return {k: v for k, v in os.environ.items() if not k.startswith("RENDER")}
