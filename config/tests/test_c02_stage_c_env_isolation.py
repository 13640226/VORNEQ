"""Regression: concurrent ledger tests must never mutate process-wide Render identity."""
from __future__ import annotations

import inspect
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.ai_ledger.tests import test_ledger_postgres as ledger_tests


class LedgerConcurrentRenderEnvironmentIsolationTests(SimpleTestCase):
    def test_explicit_concurrent_reservations_leave_render_environment_untouched(self):
        # No database I/O: reserve_with_config is mocked; the worker call shape
        # and environment invariance remain verified with real Python threads.
        with patch.dict(os.environ, {"VORNEQ_ENV": "development"}, clear=True):
            original = dict(os.environ)
            with patch.object(
                ledger_tests, "reserve_with_config",
                side_effect=lambda _config, **kwargs: kwargs,
            ) as reserve:
                with ThreadPoolExecutor(max_workers=12) as pool:
                    observed = list(pool.map(
                        lambda i: ledger_tests.do_reserve_explicit(
                            "staging" if i % 2 else "production"
                        ), range(24),
                    ))
                self.assertEqual(os.environ, original)
                self.assertEqual(reserve.call_count, 24)
                self.assertEqual({x["environment"] for x in observed},
                                 {"staging", "production"})
                for result in observed:
                    self.assertEqual(result["service_id"],
                                     ledger_tests.h.runtime(result["environment"])["RENDER_SERVICE_ID"])
                    self.assertEqual(result["git_sha"], ledger_tests.h.SHA)

    def test_parallel_ledger_call_sites_use_explicit_identity(self):
        for test_method in (
            ledger_tests.SharedLedgerPostgresTests.test_c01_twenty_simultaneous_only_three_affordable,
            ledger_tests.SharedLedgerPostgresTests.test_c02_staging_and_production_share_one_cap,
        ):
            source = inspect.getsource(test_method)
            self.assertIn("do_reserve_explicit(", source)
            self.assertNotIn("lambda i: do_reserve(", source)
