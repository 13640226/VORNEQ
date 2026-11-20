"""One-purpose Staging image MOCK E2E command; default READ ONLY.

Only --execute plus a fresh owner-issued GitHub release, an armed one-off
process and an unconsumed one-use receipt can write to Staging. The service's
own image gates are never opened; no paid provider can be reached.
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.core import staging_image_0004_runner as runner0004
from apps.core import staging_image_mock_e2e as e2e


class Command(BaseCommand):
    help = "Read-only Staging mock image E2E preflight unless --execute is fully authorized"

    def add_arguments(self, parser):
        parser.add_argument("--expected-sha", required=True)
        parser.add_argument("--execute", action="store_true")
        parser.add_argument("--release-id", default="")
        parser.add_argument("--find-residue", action="store_true",
                            help="read-only report of leftovers from interrupted runs")

    def handle(self, *args, **options):
        sha = options["expected_sha"]
        environ = os.environ
        connection = connections["default"]
        try:
            if options["find_residue"]:
                if options["execute"] or options["release_id"]:
                    raise e2e.Refused("--find-residue is read-only and stands alone")
                e2e.base_context(environ, sha, connection.settings_dict)
                runner0004.check_identity(runner0004.snapshot(connection), False)
                e2e.find_residue(out=self.stdout.write)
                return None
            e2e.inspect(connection, sha, environ=environ, out=self.stdout.write)
            if not options["execute"]:
                if options["release_id"]:
                    raise e2e.Refused("release ID is only accepted with --execute")
                self.stdout.write("STAGING_IMAGE_MOCK_E2E_RESULT: READ_ONLY_NO_GO")
                return None
            if not options["release_id"]:
                raise e2e.Refused("a scoped release ID is required")
            target = e2e.authorize(environ, sha, connection.settings_dict)
            if target.release_id != options["release_id"]:
                raise e2e.Refused("owner release ID mismatch")
            host = e2e.base_context(environ, sha, connection.settings_dict, require_arm=True)
            e2e.execute_once(connection, target, sha, public_host=host,
                             out=self.stdout.write)
            self.stdout.write("STAGING_IMAGE_MOCK_E2E_RESULT: PASS_CLEANUP_VERIFIED")
        except e2e.Refused as exc:
            raise CommandError("STAGING_IMAGE_MOCK_E2E_REFUSED: " + str(exc)) from None
        except e2e.Aborted as exc:
            raise CommandError("STAGING_IMAGE_MOCK_E2E_ABORTED: " + str(exc)) from None
        return None
