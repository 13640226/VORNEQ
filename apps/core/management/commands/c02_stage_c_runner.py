"""C02 Stage C runner command.

    python manage.py c02_stage_c_runner --target lab --expected-sha <sha> [--commit]

``--target production`` requires ``--commit`` and all SHA-bound owner and
point-of-use Production guards. No production invocation is authorized merely
by merging/deploying this source.
Without ``--commit`` an explicitly authorized *lab* rehearsal deliberately
rolls back the migration.
"""
import os
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.core import c02_stage_c_runner as runner

ROOT = Path(__file__).resolve().parents[4]


def checkout_sha() -> str:
    """Clean git checkout SHA (lab); never trusts caller input."""
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                            check=True, capture_output=True, text=True, timeout=10)
    if status.stdout.strip():
        raise CommandError("C02 Stage C refused: tracked files modified")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True, timeout=10).stdout.strip()


def deployed_sha() -> str:
    return os.environ.get("RENDER_GIT_COMMIT", "")


class Command(BaseCommand):
    help = "C02 Stage C guarded ai_core migration runner (requires explicit owner/SHA/backup authorization)"

    def add_arguments(self, parser):
        parser.add_argument("--target", choices=("lab", "production"), required=True)
        parser.add_argument("--expected-sha", required=True)
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        target_name = options["target"]
        if target_name == "production":
            if not runner.production_write_gate_open(os.environ, options["expected_sha"]):
                raise CommandError("C02 OPEN: production write path disabled (SHA-bound arm missing or mismatched)")
            if not options["commit"]:
                raise CommandError("C02 production requires explicit --commit; rehearsal is lab-only")
        source = deployed_sha if target_name == "production" else checkout_sha
        connection = connections["default"]
        try:
            target = runner.authorize(target_name, os.environ, options["expected_sha"],
                                      connection.settings_dict, source())
            result = runner.run(connection, target, options["expected_sha"], commit=options["commit"],
                                source_sha=source, out=self.stdout.write)
        except (runner.RunnerRefused, runner.RunnerAborted) as exc:
            raise CommandError(f"C02 Stage C {type(exc).__name__}: {exc}") from None
        self.stdout.write(f"C02_STAGE_C_RESULT: {result}")
        if target_name != "production":
            self.stdout.write("LAB ONLY / PRODUCTION_MIGRATION_GO=NO")
