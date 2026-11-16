"""Regression: historical C02 one-use approval does not authorize a new SHA.

Tests use wholly synthetic DATABASE_URL credentials and make no SQL/network calls.
"""
from unittest import mock

import dj_database_url
from django.test import SimpleTestCase

from apps.core import c02_stage_c_runner as runner


AUDITED_SHA = "37b2ce05ae59f984fd9181aa25395d098d24879f"
OLD_RELEASE_SHA = "6cd03395bacbde762055076f4722555f097d612a"
FAKE_URL = (
    "postgresql://vorneq_production_db_user:synthetic-only-not-a-secret"
    "@dpg-dagru1h42hec73eqr960-a/vorneq_production_db"
)


def _env(approval_sha):
    return {
        "VORNEQ_ENV": "production",
        "RENDER_SERVICE_ID": runner.PRODUCTION_SERVICE_ID,
        "RENDER_GIT_COMMIT": AUDITED_SHA,
        "VORNEQ_C02_MIGRATION_AUTH": (
            f"OWNER-AUTH-C02-MIGRATION-TEST-OLD @ {approval_sha}"
        ),
        "VORNEQ_C02_BACKUP_EVIDENCE": "test-only-synthetic-evidence",
        "VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED": "false",
        "DATABASE_URL": FAKE_URL,
    }


class C02EvidenceAuthorizationRegressionTests(SimpleTestCase):
    def test_previous_sha_approval_does_not_transfer_to_current_source(self):
        settings_dict = {
            "ENGINE": "django.db.backends.postgresql",
            **dj_database_url.parse(FAKE_URL),
        }
        # Temporarily exercise the *future* authorization specification,
        # without changing the production-write constant on disk.
        with mock.patch.object(runner, "PRODUCTION_WRITE_ENABLED", True):
            with self.assertRaisesRegex(
                runner.RunnerRefused, "SHA-bound owner authorization missing"
            ):
                runner.authorize(
                    "production", _env(OLD_RELEASE_SHA),
                    AUDITED_SHA, settings_dict, AUDITED_SHA,
                )

    def test_matching_documentary_inputs_cannot_bypass_disabled_prod_gate(self):
        settings_dict = {
            "ENGINE": "django.db.backends.postgresql",
            **dj_database_url.parse(FAKE_URL),
        }
        self.assertIs(runner.PRODUCTION_WRITE_ENABLED, False)
        with self.assertRaisesRegex(runner.RunnerRefused, "C02 OPEN"):
            runner.authorize(
                "production", _env(AUDITED_SHA),
                AUDITED_SHA, settings_dict, AUDITED_SHA,
            )
