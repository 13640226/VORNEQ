import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from apps.core.services.funktionen_audit import build_report
from config.health import release_identifier


class Command(BaseCommand):
    help = (
        "Read-only static audit of the 'How VORNEQ works' cards, their routes "
        "and all POST forms. Prints JSON to stdout; writes nothing. Exits with "
        "an error when the report is INCOMPLETE."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--templates-dir",
            default=None,
            help="Templates directory to read (default: BASE_DIR/templates).",
        )

    def handle(self, *args, **options):
        templates_dir = Path(options["templates_dir"] or Path(settings.BASE_DIR) / "templates")
        with translation.override(settings.LANGUAGE_CODE):
            report = build_report(templates_dir, release=release_identifier())
        self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        if report["status"] != "COMPLETE":
            raise CommandError("Audit report is INCOMPLETE; see findings with severity ERROR.")
