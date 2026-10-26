"""Negative tests for TASK-20 review-only preflight; no DB/network access."""
from dataclasses import replace

import pytest

from scripts.migration_wrapper_preflight import (
    PreflightRejected,
    ReviewContext,
    validate_review_context,
)

SHA = "e3d32256dbe1e79664678ca77473f6135c0c9700"


@pytest.fixture
def valid_context():
    return ReviewContext(
        approved_sha=SHA,
        observed_sha=SHA,
        database_name="vorneq_production_db",
        confirmed=True,
        allow_production=True,
        backup_reviewed=True,
        exclusive_window_reviewed=True,
    )


def test_review_context_only(valid_context):
    validate_review_context(valid_context)


@pytest.mark.parametrize("changes", [
    {"approved_sha": "not-a-sha"},
    {"observed_sha": "bad"},
    {"observed_sha": "a" * 40},
    {"database_name": "vorneq_staging_db"},
    {"confirmed": False},
    {"allow_production": False},
    {"backup_reviewed": False},
    {"exclusive_window_reviewed": False},
])
def test_fail_closed_on_invalid_review_input(valid_context, changes):
    with pytest.raises(PreflightRejected):
        validate_review_context(replace(valid_context, **changes))


def test_module_has_no_migration_or_database_execution_path():
    import inspect
    from scripts import migration_wrapper_preflight as module
    source = inspect.getsource(module)
    assert "subprocess" not in source
    assert "psycopg" not in source
    assert "execute_approved_migration" not in source
