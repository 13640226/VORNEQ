"""Explicit C02 0003 runner; production cannot be tested by invoking this command.

Lab only without --commit; production requires a separate fresh owner grant,
a SHA-bound arm and --commit. No deployment ever invokes this command implicitly.
"""
import os
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.core import c02_conversation_0003_runner as runner

ROOT = Path(__file__).resolve().parents[4]


def checkout_sha():
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=10,
    )
    if status.stdout.strip():
        raise CommandError("tracked files modified")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()


class Command(BaseCommand):
    help = "Guarded exactly-one ai_core.0003_conversation migration (lab rehearsal default)"

    def add_arguments(self, parser):
        parser.add_argument("--target", choices=("lab", "production"), required=True)
        parser.add_argument("--expected-sha", required=True)
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        name = options["target"]
        commit = bool(options["commit"])
        if name == "production":
            if not runner.arm_open(os.environ, options["expected_sha"]):
                raise CommandError("C02 0003 production arm closed (no SQL executed)")
            if not commit:
                raise CommandError("production requires --commit; rehearsal is lab-only")
            source_sha = lambda: os.environ.get("RENDER_GIT_COMMIT", "")
        else:
            source_sha = checkout_sha
        connection = connections["default"]
        try:
            target = runner.authorize(
                name, os.environ, options["expected_sha"],
                connection.settings_dict, source_sha(),
            )
            result = runner.run(
                connection, target, options["expected_sha"],
                commit=commit, source_sha=source_sha, out=self.stdout.write,
            )
        except (runner.Refused, runner.Aborted) as exc:
            raise CommandError(f"C02 0003 {type(exc).__name__}: {exc}") from None
        self.stdout.write(f"C02_CONV_0003_RESULT: {result}")
        if name == "lab":
            self.stdout.write("LAB ONLY; PRODUCTION_MIGRATION_GO=NO")
