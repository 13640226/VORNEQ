#!/usr/bin/env python3
"""TASK-20 isolated migration preflight. No database connections or migrations.

This module deliberately has NO production execution path. It checks an
explicit review context and reuses pure decision logic from db_target_guard.
It is not a production migration wrapper or a commit attestation mechanism.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

from scripts.db_target_guard import decide

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_DATABASE = "vorneq_production_db"


@dataclass(frozen=True)
class ReviewContext:
    approved_sha: str
    observed_sha: str
    database_name: str
    confirmed: bool
    allow_production: bool
    backup_reviewed: bool
    exclusive_window_reviewed: bool


class PreflightRejected(ValueError):
    pass


def validate_review_context(context: ReviewContext) -> None:
    """Check review inputs only; do NOT attest a real Render build or DB."""
    if not SHA_RE.fullmatch(context.approved_sha):
        raise PreflightRejected("invalid approved SHA")
    if not SHA_RE.fullmatch(context.observed_sha):
        raise PreflightRejected("invalid observed SHA")
    if context.approved_sha != context.observed_sha:
        raise PreflightRejected("reviewed SHAs differ")
    if context.database_name != EXPECTED_DATABASE:
        raise PreflightRejected("review database name mismatch")
    allowed, _ = decide(True, context.allow_production, context.confirmed)
    if not allowed:
        raise PreflightRejected("explicit review confirmation missing")
    if not context.backup_reviewed:
        raise PreflightRejected("backup review missing")
    if not context.exclusive_window_reviewed:
        raise PreflightRejected("exclusive window review missing")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--approved-sha", required=True)
    parser.add_argument("--observed-sha", required=True)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--confirm-review", action="store_true")
    parser.add_argument("--allow-production-review", action="store_true")
    parser.add_argument("--backup-reviewed", action="store_true")
    parser.add_argument("--exclusive-window-reviewed", action="store_true")
    args = parser.parse_args(argv)
    context = ReviewContext(
        approved_sha=args.approved_sha,
        observed_sha=args.observed_sha,
        database_name=args.database_name,
        confirmed=args.confirm_review,
        allow_production=args.allow_production_review,
        backup_reviewed=args.backup_reviewed,
        exclusive_window_reviewed=args.exclusive_window_reviewed,
    )
    try:
        validate_review_context(context)
    except PreflightRejected:
        print("REJECTED: review-only preflight did not pass")
        return 2
    print("REVIEW_ONLY_PASS: no runtime attestation, DB connection, or migration performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
