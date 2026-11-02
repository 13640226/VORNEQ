#!/usr/bin/env python3
"""Opt-in, standard-library-only static CI dispatch preflight.

No subprocesses, network, file writes, GitHub API calls, or workflow execution.
This file is NOT wired into any workflow, hook, or required check.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKIP_DIRECTIVE = re.compile(
    r"\[(?:skip ci|ci skip|no ci|skip actions|actions skip)\]",
    re.IGNORECASE,
)
SKIP_TRAILER = re.compile(r"(?im)^skip-checks:\s*true\s*$")
REQUIRED_CONTEXTS = (
    "test (3.11)",
    "test (3.12)",
    "dependencies",
    "postgres-backup-restore",
)


def inspect_message(message: str) -> list[str]:
    findings: list[str] = []
    if SKIP_DIRECTIVE.search(message):
        findings.append("CI_SKIP_DIRECTIVE_PRESENT")
    if SKIP_TRAILER.search(message):
        findings.append("CI_SKIP_TRAILER_PRESENT")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--message-file",
        type=Path,
        required=True,
        help="Existing local UTF-8 commit message file; no git/network access",
    )
    args = parser.parse_args(argv)
    try:
        message = args.message_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"PRECHECK_UNKNOWN: cannot read message: {type(exc).__name__}", file=sys.stderr)
        return 2
    findings = inspect_message(message)
    if findings:
        print("PRECHECK_BLOCKED: " + ", ".join(findings))
        print("Required checks may remain Expected; do not trigger CI without authorization.")
        return 1
    print("PRECHECK_MESSAGE_OK: no known skip directive in inspected message")
    print("NOT a guarantee of workflow dispatch, safety, or check completion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
