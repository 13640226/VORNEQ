"""Production read-only preflight; intentionally no commit or execute flag."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.core import production_image_0004_preflight as preflight


class Command(BaseCommand):
    help = "Inspect the exact Production image 0004 plan; never migrate."

    def add_arguments(self, parser):
        parser.add_argument("--expected-sha", required=True)

    def handle(self, *args, **options):
        try:
            result = preflight.inspect(connections["default"], options["expected_sha"])
        except preflight.PreflightDenied as exc:
            raise CommandError("PRODUCTION_IMAGE_0004_DENIED: " + str(exc)) from None
        except Exception as exc:
            raise CommandError("PRODUCTION_IMAGE_0004_DENIED: " + type(exc).__name__) from None
        self.stdout.write(json.dumps(result, sort_keys=True))
        self.stdout.write("PRODUCTION_IMAGE_0004_MIGRATION_GO: NO; READ_ONLY")
