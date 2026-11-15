"""Print a secret-free operational binding report (no SQL, no writes).

Run in the Render Web Shell of the Production service:

    python manage.py c02_internal_url_binding --nonce <fresh 64-hex nonce>

Then compare C02_DATABASE_URL_HMAC_SHA256 with the digest of the Dashboard
Internal URL computed locally by scripts/c02_tests/internal_url_digest.py.
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.core.c02_operational_binding import BindingError, binding_report


class Command(BaseCommand):
    help = "C02: HMAC digest of DATABASE_URL for Dashboard comparison; never connects or migrates"

    def add_arguments(self, parser):
        parser.add_argument("--nonce", required=True)

    def handle(self, *args, **options):
        try:
            report = binding_report(os.environ, connections["default"].settings_dict, options["nonce"])
        except BindingError as exc:
            raise CommandError(f"C02 binding report refused: {exc}") from None
        for key, value in report.items():
            self.stdout.write(f"{key}: {value}")
        self.stdout.write("NO SQL EXECUTED / NO MIGRATION GO")
