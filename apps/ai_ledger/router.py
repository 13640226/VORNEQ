"""Route the shared AI budget ledger to its own database alias ONLY.

The ledger is a single authority shared by Staging and Production; it must
never be created inside either application database, and no application
model may be migrated into the ledger database.
"""
LEDGER_ALIAS = "ai_ledger"
LEDGER_APP = "ai_ledger"


class AILedgerRouter:
    def db_for_read(self, model, **hints):
        return LEDGER_ALIAS if model._meta.app_label == LEDGER_APP else None

    def db_for_write(self, model, **hints):
        return LEDGER_ALIAS if model._meta.app_label == LEDGER_APP else None

    def allow_relation(self, obj1, obj2, **hints):
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        if LEDGER_APP in labels:
            return labels == {LEDGER_APP}
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == LEDGER_APP:
            return db == LEDGER_ALIAS
        if db == LEDGER_ALIAS:
            return False
        return None
