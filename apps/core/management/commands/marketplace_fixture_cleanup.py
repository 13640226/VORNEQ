"""One-time audited Marketplace fixture cleanup; preview is the default.

Do not use this command for ordinary data maintenance or other fixtures.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from marketplace.fixture_cleanup import (
    BACKUP_DIGEST,
    OWNER_REFERENCE,
    FixtureCleanupRejected,
    cleanup,
)


class Command(BaseCommand):
    help = (
        "Preview a strictly pinned 501-product fixture cleanup. "
        "Production writes require separate owner-authorized environment gates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Attempt one-time audited cleanup, subject to fail-closed release gates.",
        )
        parser.add_argument(
            "--acknowledge-empty-catalog", choices=["501"],
            help="Required with --apply: acknowledge the public catalog will be empty.",
        )
        parser.add_argument(
            "--backup-sha256",
            help="Required with --apply: hash of independently restored full backup.",
        )
        parser.add_argument(
            "--owner-reference",
            help="Required with --apply: independent owner authorization reference.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        if apply and not (
            options["acknowledge_empty_catalog"] == "501"
            and options["backup_sha256"] == BACKUP_DIGEST
            and options["owner_reference"] == OWNER_REFERENCE
        ):
            raise CommandError("STOP_RELEASE_APPROVAL_ARGUMENTS")
        try:
            result = cleanup(apply=apply)
        except (FixtureCleanupRejected, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        # Machine-readable evidence; never log credentials or product metadata.
        self.stdout.write(json.dumps(result, sort_keys=True))
