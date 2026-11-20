"""One-purpose ai_core.0004 staging migration command; default READ ONLY.

Only --commit plus fresh owner-issued GitHub release proof can modify Staging.
Never invoke bare manage.py migrate to bypass db_target_guard or workflow stops.
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.core import staging_image_0004_runner as runner


class Command(BaseCommand):
    help = "Read-only Staging 0004 preflight unless one-use --commit is fully authorized"

    def add_arguments(self, parser):
        parser.add_argument("--expected-sha", required=True)
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--release-id", default="")

    def handle(self, *args, **options):
        sha = options["expected_sha"]
        environ = os.environ
        connection = connections["default"]
        try:
            if options["commit"]:
                if not options["release_id"]:
                    raise runner.Refused("a scoped release ID is required")
                target = runner.authorize(environ, sha, connection.settings_dict)
                if target.release_id != options["release_id"]:
                    raise runner.Refused("owner release ID mismatch")
                result = runner.apply_once(
                    connection, target, sha, environ=environ, out=self.stdout.write
                )
                self.stdout.write("STAGING_IMAGE_0004_RELEASE_RESULT: COMMITTED_VERIFIED")
            else:
                if options["release_id"]:
                    raise runner.Refused("release ID is only accepted with --commit")
                result = runner.inspect(
                    connection, sha, environ=environ, out=self.stdout.write
                )
                self.stdout.write("STAGING_IMAGE_0004_RELEASE_RESULT: READ_ONLY_NO_GO")
        except (runner.Refused, runner.Aborted) as exc:
            raise CommandError("STAGING_IMAGE_0004_DENIED: " + str(exc)) from None
        return None
