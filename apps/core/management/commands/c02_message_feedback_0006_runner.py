"""Exact 0006 runner. Default local inspect; hosted commit is separately armed."""
import os
import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from apps.core import c02_message_feedback_0006_runner as runner
from apps.core import c02_message_feedback_0006_hosted as hosted


def source_sha(expected=None, *, separate=False):
    root = Path(__file__).resolve().parents[4]
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
            raise runner.Refused("source root mismatch")
        if separate:
            # Never change the deployed application directory or spoof its SHA.
            if (not isinstance(expected, str) or not hosted.release.SHA.fullmatch(expected)
                    or root != Path("/tmp") / ("vorneq-c02-0006-" + expected)
                    or Path.cwd().resolve() != root):
                raise runner.Refused("separate schema-first checkout required")
            if git("remote", "get-url", "origin") not in (
                    "https://github.com/13640226/VORNEQ.git",
                    "https://github.com/13640226/VORNEQ"):
                raise runner.Refused("unexpected repository origin")
        if git("status", "--porcelain", "--untracked-files=all"):
            raise runner.Refused("source checkout is dirty")
        if any(line.startswith("S ") or (line and line[0].islower())
               for line in git("ls-files", "-v").splitlines()):
            raise runner.Refused("hidden index state forbidden")
        # Ignored executable sources can shadow tracked imports.
        if separate and any(p.endswith((".py", ".pth", ".so", ".pyd"))
                            for p in git("ls-files", "--others", "--ignored",
                                         "--exclude-standard").splitlines()):
            raise runner.Refused("ignored executable source forbidden")
        return git("rev-parse", "HEAD")
    except (OSError, subprocess.SubprocessError):
        raise runner.Refused("source SHA unavailable") from None


class Command(BaseCommand):
    requires_system_checks = []
    requires_migrations_checks = False
    help = "C02 0006 exact-plan lab or independently authorized schema-first executor"

    def add_arguments(self, parser):
        parser.add_argument("--expected-sha", required=True)
        parser.add_argument("--mode", choices=("inspect", "rehearse", "lab_commit", "hosted_commit"),
                            default="inspect")
        parser.add_argument("--environment", choices=("staging", "production"))
        parser.add_argument("--expected-live-sha")
        parser.add_argument("--release-id")

    def handle(self, *args, **options):
        mode = options["mode"]
        sha = options["expected_sha"]
        try:
            if mode == "hosted_commit":
                if not all(options[k] for k in ("environment", "expected_live_sha", "release_id")):
                    raise runner.Refused("explicit hosted scope required")
                result = hosted.run_hosted(
                    connections["default"], environment=options["environment"],
                    expected_sha=sha, live_sha=options["expected_live_sha"],
                    release_id=options["release_id"],
                    artifact_sha=lambda: source_sha(sha, separate=True), environ=os.environ,
                )
            else:
                if any(options[k] for k in ("environment", "expected_live_sha", "release_id")):
                    raise runner.Refused("hosted scope is forbidden in lab")
                result = runner.run(connections["default"], sha,
                                    source_sha=source_sha, mode=mode)
        except (runner.Refused, runner.Aborted) as exc:
            raise CommandError("C02_0006_DENIED: " + str(exc)) from None
        self.stdout.write(str(result))
