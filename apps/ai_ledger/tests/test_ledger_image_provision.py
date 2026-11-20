"""ai_ledger_image_provision: dry run by default, staging-only, official prices, chat untouched.

Synthetic ids only; no provider, no network. Write paths need PostgreSQL.
"""
import uuid
from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.ai_core.image_generation.policy import OFFICIAL_PRICES_MICRO_PER_MTOK
from apps.ai_ledger.models import BudgetAccount
from apps.ai_ledger.tests import helpers as h
from apps.ai_ledger.tests.test_ledger_postgres import IS_PG, LEDGER_ALIAS

IMAGE_ID = uuid.UUID("77777777-2222-4333-8444-555555555555")
BASE = {"VORNEQ_AI_IMAGE_LEDGER_ID": str(IMAGE_ID), "VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD": 100_000}


def run(*args):
    out = StringIO()
    call_command("ai_ledger_image_provision", *args, stdout=out)
    return out.getvalue()


def args(total="2.00", safety="0.50", ledger=str(IMAGE_ID)):
    return ["--ledger-id", ledger, "--total-usd", total, "--safety-usd", safety]


@override_settings(**h.ledger_settings(), **BASE)
class ImageProvisionPlanTests(SimpleTestCase):
    def test_dry_run_is_default_and_never_opens_the_ledger(self):
        with patch("apps.ai_ledger.management.commands.ai_ledger_image_provision._verify_identity",
                   side_effect=AssertionError("database touched")):
            out = run(*args())
        self.assertIn("RESULT=DRY_RUN_NO_DATABASE_ACCESS", out)
        self.assertIn("PLAN allowed_environments=staging", out)
        self.assertIn("PLAN emergency_stop=True", out)
        self.assertIn("PLAN model_id=gpt-image-2.6-flare", out)
        self.assertNotIn(str(IMAGE_ID), out)

    def test_guards_refuse_unsafe_plans(self):
        cases = [
            (args(ledger=str(uuid.uuid4())), "VORNEQ_AI_IMAGE_LEDGER_ID"),
            (args(total="5.01"), "--total-usd"),
            (args(total="0"), "--total-usd"),
            (args(total="0.55", safety="0.50"), "maximum-cost request"),
            (args(ledger="not-a-uuid"), "valid UUID"),
        ]
        for argv, message in cases:
            with self.subTest(argv=argv), self.assertRaisesMessage(CommandError, message):
                run(*argv)

    def test_refuses_chat_ledger_id_and_missing_request_cap(self):
        with override_settings(VORNEQ_AI_IMAGE_LEDGER_ID=str(h.LEDGER_ID)):
            with self.assertRaisesMessage(CommandError, "must differ"):
                run(*args(ledger=str(h.LEDGER_ID)))
        with override_settings(VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD=0):
            with self.assertRaisesMessage(CommandError, "MAX_REQUEST"):
                run(*args())

    def test_execute_requires_confirmation(self):
        with self.assertRaisesMessage(CommandError, "--confirm-ledger-id"):
            run(*args(), "--execute")


@skipUnless(IS_PG, "shared ledger requires PostgreSQL")
class ImageProvisionExecuteTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        # Resolved at run time: the test database name is only known after setup.
        override = override_settings(**h.ledger_settings(), **BASE)
        override.enable()
        self.addCleanup(override.disable)
        self.chat = h.provision(3)
        self.chat_before = BudgetAccount.objects.using(LEDGER_ALIAS).filter(pk=self.chat.pk).values().get()

    def test_execute_creates_one_locked_staging_account_and_leaves_chat_alone(self):
        out = run(*args(), "--confirm-ledger-id", str(IMAGE_ID), "--execute")
        self.assertIn("RESULT=IMAGE_ACCOUNT_CREATED_EMERGENCY_STOP_ON", out)
        image = BudgetAccount.objects.using(LEDGER_ALIAS).get(ledger_id=IMAGE_ID)
        self.assertEqual((image.allowed_environments, image.emergency_stop, image.model_id),
                         ("staging", True, "gpt-image-2.6-flare"))
        self.assertEqual((image.input_price_micro_per_mtok, image.output_price_micro_per_mtok),
                         OFFICIAL_PRICES_MICRO_PER_MTOK["gpt-image-2.6-flare"])
        self.assertEqual((image.total_allowance_micro, image.safety_reserve_micro), (2_000_000, 500_000))
        self.assertEqual(BudgetAccount.objects.using(LEDGER_ALIAS).filter(pk=self.chat.pk).values().get(),
                         self.chat_before)
        with self.assertRaisesMessage(CommandError, "already exists"):
            run(*args(total="1.00"), "--confirm-ledger-id", str(IMAGE_ID), "--execute")
        self.assertEqual(BudgetAccount.objects.using(LEDGER_ALIAS).get(ledger_id=IMAGE_ID)
                         .total_allowance_micro, 2_000_000)

    def test_identity_mismatch_writes_nothing(self):
        with override_settings(VORNEQ_AI_LEDGER_DB_NAME="wrong_ledger_db"):
            with self.assertRaisesMessage(CommandError, "identity mismatch"):
                run(*args(), "--confirm-ledger-id", str(IMAGE_ID), "--execute")
        self.assertFalse(BudgetAccount.objects.using(LEDGER_ALIAS).filter(ledger_id=IMAGE_ID).exists())
