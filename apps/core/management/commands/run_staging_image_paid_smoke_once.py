"""One-purpose Staging PAID image smoke command; default READ ONLY (NO_GO).

Only --execute plus a fresh owner-issued GitHub release, an armed one-off
process, a GO preflight and an unconsumed one-use receipt can make exactly one
paid OpenAI image request for one disposable user. No Worker, no retry.
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.core import staging_image_paid_smoke as smoke


class Command(BaseCommand):
    help = "Read-only Staging paid image smoke preflight unless --execute is fully authorized"

    def add_arguments(self, parser):
        parser.add_argument("--expected-sha", required=True)
        parser.add_argument("--execute", action="store_true")
        parser.add_argument("--release-id", default="")
        parser.add_argument("--ledger-audit", action="store_true",
                            help="read-only shared-ledger inventory (identity, schema, accounts)")

    def handle(self, *args, **options):
        sha = options["expected_sha"]
        environ = os.environ
        connection = connections["default"]
        try:
            if options["ledger_audit"]:
                if options["execute"] or options["release_id"]:
                    raise smoke.Refused("--ledger-audit is read-only and stands alone")
                smoke.e2e.base_context(environ, sha, connection.settings_dict)
                smoke.ledger_audit(out=self.stdout.write)
                return None
            if not options["execute"]:
                if options["release_id"]:
                    raise smoke.Refused("release ID is only accepted with --execute")
                smoke.preflight(connection, sha, environ=environ, out=self.stdout.write)
                self.stdout.write("STAGING_IMAGE_PAID_SMOKE_RESULT: READ_ONLY_NO_GO")
                return None
            if not options["release_id"]:
                raise smoke.Refused("a scoped release ID is required")
            target = smoke.authorize(environ, sha, connection.settings_dict)
            if target.release_id != options["release_id"]:
                raise smoke.Refused("owner release ID mismatch")
            checks = smoke.preflight(connection, sha, environ=environ, out=self.stdout.write,
                                     cap_micro=target.max_cost_micro,
                                     expected_image_ledger_id=target.image_ledger_id)
            if not checks.go:
                raise smoke.Refused("preflight is NO_GO")
            host = smoke.e2e.base_context(environ, sha, connection.settings_dict)
            smoke.execute_once(connection, target, sha, public_host=host,
                               out=self.stdout.write)
            self.stdout.write("STAGING_IMAGE_PAID_SMOKE_RESULT: PASS_CLEANUP_VERIFIED")
        except smoke.Refused as exc:
            raise CommandError("STAGING_IMAGE_PAID_SMOKE_REFUSED: " + str(exc)) from None
        except smoke.Aborted as exc:
            raise CommandError("STAGING_IMAGE_PAID_SMOKE_ABORTED: " + str(exc)) from None
        return None
