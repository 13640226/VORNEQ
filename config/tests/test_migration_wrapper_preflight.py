"""Negative tests for TASK-20 review-only preflight; no DB/network access."""
import inspect
import unittest
from dataclasses import replace

from scripts import migration_wrapper_preflight as module
from scripts.migration_wrapper_preflight import (
    PreflightRejected,
    ReviewContext,
    validate_review_context,
)

SHA = "e3d32256dbe1e79664678ca77473f6135c0c9700"

INVALID_CHANGES = [
    {"approved_sha": "not-a-sha"},
    {"observed_sha": "bad"},
    {"observed_sha": "a" * 40},
    {"database_name": "vorneq_staging_db"},
    {"confirmed": False},
    {"allow_production": False},
    {"backup_reviewed": False},
    {"exclusive_window_reviewed": False},
]


class MigrationWrapperPreflightTests(unittest.TestCase):
    def setUp(self):
        self.valid_context = ReviewContext(
            approved_sha=SHA,
            observed_sha=SHA,
            database_name="vorneq_production_db",
            confirmed=True,
            allow_production=True,
            backup_reviewed=True,
            exclusive_window_reviewed=True,
        )

    def test_valid_review_context_is_rejected_while_guard_is_fail_closed(self):
        # db_target_guard.decide() is fail-closed on main until independent
        # attestation and single-use authorization exist, so even a fully
        # valid review context must be rejected. The preflight is inert.
        with self.assertRaises(PreflightRejected) as ctx:
            validate_review_context(self.valid_context)
        self.assertIn("explicit review confirmation missing", str(ctx.exception))

    def test_fail_closed_on_invalid_review_input(self):
        for changes in INVALID_CHANGES:
            with self.subTest(changes=changes):
                with self.assertRaises(PreflightRejected):
                    validate_review_context(replace(self.valid_context, **changes))

    def test_module_has_no_migration_or_database_execution_path(self):
        source = inspect.getsource(module)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("psycopg", source)
        self.assertNotIn("execute_approved_migration", source)


if __name__ == "__main__":
    unittest.main()
