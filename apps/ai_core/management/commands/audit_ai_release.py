"""Read-only operator diagnostics for Chat and Image Studio release gates."""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.ai_core.release_diagnostics import build_report
from apps.core.management.commands.audit_runtime import identity


class Command(BaseCommand):
    help = "Report secret-free AI gate diagnostics; optionally read GitHub evidence."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--environment", required=True, choices=("staging", "production"))
        parser.add_argument("--expected-sha", required=True)
        parser.add_argument("--verify-release", action="store_true")

    def handle(self, *args, **options):
        environment = options["environment"]
        identity(environment, options["expected_sha"], False)
        try:
            report = build_report(environment, verify=options["verify_release"])
        except Exception:
            raise CommandError("AI_RELEASE_DIAGNOSTIC_INCOMPLETE") from None
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
