"""Production image expense journal. Does not grant provider or worker access."""
from __future__ import annotations
import uuid
from django.db import transaction
from django.utils import timezone
from apps.ai_ledger.service import LEDGER_ALIAS, LedgerUnavailable, EmergencyStop, _verify_identity


def record_production_image_intent(config, *, request_id, actor_id, service_id, git_sha, model, estimated_micro):
    """Atomic idempotent accounting only; caller must separately authorize paid calls."""
    from apps.ai_ledger.models import BudgetAccount, ProductionImageUsage
    from apps.ai_core.image_generation.policy import PRODUCTION_SERVICE_ID, production_uncapped_budget_requested
    from apps.ai_core.image_generation.policy import image_ledger_config
    if (type(request_id) is not uuid.UUID or request_id.version != 4
            or type(actor_id) is not int or actor_id != 1
            or service_id != PRODUCTION_SERVICE_ID
            or not production_uncapped_budget_requested()
            or type(estimated_micro) is not int or estimated_micro <= 0
            or not isinstance(model, str) or not model
            or config != image_ledger_config()):
        raise LedgerUnavailable("uncapped Production image accounting not authorized")
    import os
    if git_sha != os.getenv("RENDER_GIT_COMMIT"):
        raise LedgerUnavailable("Production image SHA mismatch")
    try:
        with transaction.atomic(using=LEDGER_ALIAS):
            _verify_identity(config.expected_db_name)
            account = BudgetAccount.objects.using(LEDGER_ALIAS).select_for_update().get(ledger_id=config.ledger_id)
            if account.emergency_stop:
                raise EmergencyStop("image ledger stopped")
            if "production" not in account.allowed_environments.split(",") or account.model_id != model:
                raise LedgerUnavailable("image ledger account mismatch")
            row, created = ProductionImageUsage.objects.using(LEDGER_ALIAS).get_or_create(
                id=request_id, defaults={"account": account, "actor_id": actor_id,
                "service_id": service_id, "git_sha": git_sha, "model_id": model,
                "estimated_micro": estimated_micro})
            if (row.account_id != account.pk or row.actor_id != actor_id
                    or row.service_id != service_id or row.git_sha != git_sha
                    or row.model_id != model or row.estimated_micro != estimated_micro):
                raise LedgerUnavailable("image accounting request ID conflict")
            return row.id, created
    except (LedgerUnavailable, EmergencyStop):
        raise
    except Exception as exc:
        raise LedgerUnavailable("Production image journal unavailable") from exc


def reconcile_production_image(request_id, *, observed_micro=None, outcome=""):
    """A sent request without trustworthy usage becomes UNCERTAIN, never zero."""
    from apps.ai_ledger.models import ProductionImageUsage
    if type(request_id) is not uuid.UUID or request_id.version != 4:
        raise LedgerUnavailable("invalid Production image request ID")
    if observed_micro is not None and (type(observed_micro) is not int or observed_micro < 0):
        raise LedgerUnavailable("invalid observed cost")
    try:
        with transaction.atomic(using=LEDGER_ALIAS):
            row = ProductionImageUsage.objects.using(LEDGER_ALIAS).select_for_update().get(pk=request_id)
            if row.status != ProductionImageUsage.RESERVED:
                return False
            row.status = ProductionImageUsage.FINALIZED if observed_micro is not None else ProductionImageUsage.UNCERTAIN
            row.observed_micro = observed_micro
            row.outcome = str(outcome)[:40]
            row.settled_at = timezone.now()
            row.save(using=LEDGER_ALIAS, update_fields=["status", "observed_micro", "outcome", "settled_at"])
            return True
    except Exception as exc:
        raise LedgerUnavailable("Production image reconciliation unavailable") from exc
