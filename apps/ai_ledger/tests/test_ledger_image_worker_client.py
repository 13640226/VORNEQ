"""The paid Staging image Worker is a ledger client ONLY for the image account.

Synthetic ids; real PostgreSQL row locks (disposable test database). No provider.
"""
import os
import uuid
from unittest import skipUnless
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase, override_settings

from apps.ai_ledger.models import BudgetAccount, BudgetReservation
from apps.ai_ledger.service import LedgerConfig, LedgerUnavailable, reserve_with_config
from apps.ai_ledger.tests import helpers as h
from apps.ai_ledger.tests.test_ledger_postgres import IS_PG, LEDGER_ALIAS

IMAGE_ID = uuid.UUID("66666666-2222-4333-8444-555555555555")
WORKER = "srv-wwwwwwwwwwwwwwwwwwww"
WEB = "srv-dbm7dvc9v7es7393g70g"
PRODUCTION = "srv-dadn07eq1p3s73eccau0"


@skipUnless(IS_PG, "real PostgreSQL row locking required")
class ImageWorkerLedgerClientTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        override = override_settings(**h.ledger_settings(), VORNEQ_AI_IMAGE_LEDGER_ID=str(IMAGE_ID),
                                     VORNEQ_AI_IMAGE_WORKER_SERVICE_ID=WORKER,
                                     VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED=True)
        override.enable()
        self.addCleanup(override.disable)
        env = patch.dict(os.environ, {"RENDER_SERVICE_ID": WORKER, "RENDER_GIT_COMMIT": h.SHA})
        env.start()
        self.addCleanup(env.stop)
        self.accounts = BudgetAccount.objects.using(LEDGER_ALIAS)
        self.chat = h.provision(3, allowed_environments="staging,production")
        self.chat_before = self.accounts.filter(pk=self.chat.pk).values().get()
        self.image = h.provision(3, ledger_id=IMAGE_ID, allowed_environments="staging")

    def reserve(self, ledger_id=IMAGE_ID, *, environment="staging", service_id=WORKER):
        config = LedgerConfig(ledger_id, connections[LEDGER_ALIAS].settings_dict["NAME"])
        return reserve_with_config(
            config, environment=environment, service_id=service_id, git_sha=h.SHA, actor_id=7,
            model=h.MODEL, input_bytes=h.INPUT_BYTES, max_output_tokens=h.MAX_OUT)

    def assert_refused(self, **kwargs):
        before = BudgetReservation.objects.using(LEDGER_ALIAS).count()
        with self.assertRaises(LedgerUnavailable):
            self.reserve(**kwargs)
        self.assertEqual(BudgetReservation.objects.using(LEDGER_ALIAS).count(), before)

    def assert_chat_unchanged(self):
        self.assertEqual(self.accounts.filter(pk=self.chat.pk).values().get(), self.chat_before)

    def test_worker_reserves_on_staging_only_image_account(self):
        res = self.reserve()
        row = BudgetReservation.objects.using(LEDGER_ALIAS).get(pk=res.id)
        self.assertEqual((row.account_id, row.environment, row.service_id),
                         (self.image.pk, "staging", WORKER))
        self.assert_chat_unchanged()

    def test_worker_can_never_reserve_on_the_chat_account(self):
        self.assert_refused(ledger_id=h.LEDGER_ID)
        with override_settings(VORNEQ_AI_IMAGE_LEDGER_ID=str(h.LEDGER_ID)):
            self.assert_refused(ledger_id=h.LEDGER_ID)
        # Even a staging-only chat account is never reachable by the worker identity.
        self.accounts.filter(pk=self.chat.pk).update(allowed_environments="staging")
        self.chat_before["allowed_environments"] = "staging"
        self.assert_refused(ledger_id=h.LEDGER_ID)
        self.assert_chat_unchanged()

    def test_worker_needs_switch_identity_and_staging(self):
        with override_settings(VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED=False):
            self.assert_refused()
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": "srv-otherotherotherother"}):
            self.assert_refused()
        self.assert_refused(service_id="srv-otherotherotherother")
        self.assert_refused(environment="production")
        # WEB is the regular web client (covered below), not a worker identity.
        for worker in (PRODUCTION, "not-a-service"):
            with self.subTest(worker=worker), override_settings(VORNEQ_AI_IMAGE_WORKER_SERVICE_ID=worker):
                with patch.dict(os.environ, {"RENDER_SERVICE_ID": worker}):
                    self.assert_refused(service_id=worker)

    def test_worker_refused_when_image_account_is_not_staging_only(self):
        self.accounts.filter(pk=self.image.pk).update(allowed_environments="staging,production")
        self.assert_refused()
        self.assert_chat_unchanged()

    def test_web_and_production_clients_are_unchanged(self):
        self.assertIsNotNone(self.reserve(service_id=WEB))
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": PRODUCTION}):
            config = LedgerConfig(h.LEDGER_ID, connections[LEDGER_ALIAS].settings_dict["NAME"])
            self.assertIsNotNone(reserve_with_config(
                config, environment="production", service_id=PRODUCTION, git_sha=h.SHA,
                actor_id=7, model=h.MODEL, input_bytes=h.INPUT_BYTES, max_output_tokens=h.MAX_OUT))
