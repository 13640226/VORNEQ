"""ai_ledger_image_control: only the staging image account, chat never touched.

Synthetic ids only; no provider, no network. Ledger paths need PostgreSQL.
"""
import uuid
from io import StringIO
from unittest import skipUnless

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.ai_core.image_generation.policy import OFFICIAL_PRICES_MICRO_PER_MTOK
from apps.ai_ledger.models import BudgetAccount
from apps.ai_ledger.tests import helpers as h
from apps.ai_ledger.tests.test_ledger_postgres import IS_PG, LEDGER_ALIAS

IMAGE_ID = uuid.UUID("88888888-2222-4333-8444-555555555555")
MODEL = "gpt-image-2.6-flare"
IN_PRICE, OUT_PRICE = OFFICIAL_PRICES_MICRO_PER_MTOK[MODEL]


def run(action, *extra, ledger=str(IMAGE_ID)):
    out = StringIO()
    call_command("ai_ledger_image_control", action, "--ledger-id", ledger, *extra, stdout=out)
    return out.getvalue()


def confirm(value=str(IMAGE_ID)):
    return ("--confirm-ledger-id", value)


@override_settings(VORNEQ_AI_IMAGE_LEDGER_ID=str(IMAGE_ID))
class ImageControlArgumentTests(SimpleTestCase):
    def test_wrong_or_invalid_id_is_refused_before_any_database_access(self):
        for ledger, message in ((str(uuid.uuid4()), "VORNEQ_AI_IMAGE_LEDGER_ID"),
                                ("not-a-uuid", "valid UUID")):
            with self.subTest(ledger=ledger), self.assertRaisesMessage(CommandError, message):
                run("status", ledger=ledger)

    def test_write_actions_require_matching_confirmation(self):
        for action in ("stop", "resume"):
            for extra in ((), confirm(str(uuid.uuid4()))):
                with self.subTest(action=action, extra=extra), \
                        self.assertRaisesMessage(CommandError, "--confirm-ledger-id"):
                    run(action, *extra)


@skipUnless(IS_PG, "shared ledger requires PostgreSQL")
class ImageControlLedgerTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        # Resolved at run time: the test database name is only known after setup.
        override = override_settings(**h.ledger_settings(), VORNEQ_AI_IMAGE_LEDGER_ID=str(IMAGE_ID))
        override.enable()
        self.addCleanup(override.disable)
        self.accounts = BudgetAccount.objects.using(LEDGER_ALIAS)
        self.chat = h.provision(3)
        self.chat_before = self.accounts.filter(pk=self.chat.pk).values().get()

    def image(self, **fields):
        values = {"ledger_id": IMAGE_ID, "total_allowance_micro": 2_000_000,
                  "safety_reserve_micro": 500_000, "model_id": MODEL,
                  "input_price_micro_per_mtok": IN_PRICE, "output_price_micro_per_mtok": OUT_PRICE,
                  "allowed_environments": "staging", "emergency_stop": True}
        values.update(fields)
        return self.accounts.create(**values)

    def stop_state(self):
        return self.accounts.get(ledger_id=IMAGE_ID).emergency_stop

    def assert_chat_unchanged(self):
        self.assertEqual(self.accounts.filter(pk=self.chat.pk).values().get(), self.chat_before)

    def test_status_is_read_only_and_redacted(self):
        self.image()
        out = run("status")
        self.assertIn("RESULT=READ_ONLY_STATUS", out)
        self.assertIn("read_only_txn=on", out)
        self.assertIn("emergency_stop=True", out)
        self.assertIn("problems=none", out)
        self.assertNotIn(str(IMAGE_ID), out)
        self.assertTrue(self.stop_state())

    def test_resume_then_stop_changes_only_the_image_flag(self):
        self.image()
        self.assertIn("RESULT=IMAGE_ACCOUNT_RESUMED", run("resume", *confirm()))
        self.assertFalse(self.stop_state())
        self.assertIn("RESULT=IMAGE_ACCOUNT_STOPPED", run("stop", *confirm()))
        self.assertTrue(self.stop_state())
        self.assert_chat_unchanged()

    def test_chat_ledger_id_can_never_be_selected(self):
        self.image()
        with override_settings(VORNEQ_AI_IMAGE_LEDGER_ID=str(h.LEDGER_ID)):
            with self.assertRaisesMessage(CommandError, "must differ"):
                run("resume", *confirm(str(h.LEDGER_ID)), ledger=str(h.LEDGER_ID))
        self.assert_chat_unchanged()

    def test_unsafe_account_is_refused_and_unchanged(self):
        cases = [({"allowed_environments": "staging,production"}, "staging-only"),
                 ({"model_id": "other-model"}, "image model"),
                 ({"output_price_micro_per_mtok": OUT_PRICE - 1}, "official price")]
        for fields, message in cases:
            with self.subTest(fields=fields):
                self.accounts.filter(ledger_id=IMAGE_ID).delete()
                self.image(**fields)
                for action in ("resume", "stop"):
                    with self.assertRaisesMessage(CommandError, message):
                        run(action, *confirm())
                self.assertTrue(self.stop_state())
        self.assert_chat_unchanged()

    def test_resume_refused_while_uncertain_or_reserved(self):
        for fields in ({"uncertain_micro": 1}, {"reserved_micro": 1}):
            with self.subTest(fields=fields):
                self.accounts.filter(ledger_id=IMAGE_ID).delete()
                self.image(**fields)
                with self.assertRaisesMessage(CommandError, "reconciled"):
                    run("resume", *confirm())
                self.assertTrue(self.stop_state())
                self.assertIn("RESULT=IMAGE_ACCOUNT_STOPPED", run("stop", *confirm()))

    def test_missing_account_or_identity_mismatch_changes_nothing(self):
        with self.assertRaisesMessage(CommandError, "does not exist"):
            run("resume", *confirm())
        self.image()
        with override_settings(VORNEQ_AI_LEDGER_DB_NAME="wrong_ledger_db"):
            with self.assertRaisesMessage(CommandError, "identity mismatch"):
                run("resume", *confirm())
        self.assertTrue(self.stop_state())
        self.assert_chat_unchanged()
