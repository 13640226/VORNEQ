from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Entitlement
from apps.core.services.registry import resolve_artifact, resolve_identity_for_user


class Command(BaseCommand):
    help = (
        "Backfill Entitlement canonical identity/artifact fields from existing "
        "UserIdentity and ArtifactBinding records. Never creates registry objects."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate the backfill without persisting changes.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Persist eligible canonical field updates.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Process at most this many Entitlements, ordered by primary key.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print one audit line per processed Entitlement.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        limit = options["limit"]
        verbose = options["verbose"]

        if dry_run == force:
            raise CommandError("Choose exactly one of --dry-run or --force.")
        if limit is not None and limit <= 0:
            raise CommandError("--limit must be a positive integer.")

        queryset = Entitlement.objects.select_related(
            "user", "product", "identity", "artifact"
        ).order_by("pk")
        if limit is not None:
            queryset = queryset[:limit]

        counts = {
            "processed": 0,
            "updated": 0,
            "already_canonical": 0,
            "unresolved": 0,
            "conflicts": 0,
        }

        with transaction.atomic():
            for entitlement in queryset:
                counts["processed"] += 1
                identity = resolve_identity_for_user(entitlement.user)
                artifact = resolve_artifact(entitlement.product)

                # The database check constraint should make partial canonical state
                # impossible. Treat it as an integrity anomaly if encountered.
                has_identity = entitlement.identity_id is not None
                has_artifact = entitlement.artifact_id is not None
                if has_identity != has_artifact:
                    counts["conflicts"] += 1
                    self._audit(verbose, "CONFLICT", entitlement, "partial canonical pair")
                    continue

                if identity is None or artifact is None:
                    counts["unresolved"] += 1
                    missing = []
                    if identity is None:
                        missing.append("UserIdentity")
                    if artifact is None:
                        missing.append("ArtifactBinding")
                    self._audit(verbose, "UNRESOLVED", entitlement, ", ".join(missing))
                    continue

                if has_identity and has_artifact:
                    if (
                        entitlement.identity_id != identity.pk
                        or entitlement.artifact_id != artifact.pk
                    ):
                        counts["conflicts"] += 1
                        self._audit(
                            verbose,
                            "CONFLICT",
                            entitlement,
                            "canonical pair disagrees with current registry bindings",
                        )
                        continue
                    counts["already_canonical"] += 1
                    self._audit(verbose, "OK", entitlement, "already canonical")
                    continue

                duplicate = Entitlement.objects.filter(
                    identity=identity,
                    artifact=artifact,
                ).exclude(pk=entitlement.pk).exists()
                if duplicate:
                    counts["conflicts"] += 1
                    self._audit(
                        verbose,
                        "CONFLICT",
                        entitlement,
                        "canonical pair is already assigned to another Entitlement",
                    )
                    continue

                if force:
                    entitlement.identity = identity
                    entitlement.artifact = artifact
                    entitlement.full_clean()
                    entitlement.save(update_fields=["identity", "artifact"])

                counts["updated"] += 1
                self._audit(
                    verbose,
                    "WOULD UPDATE" if dry_run else "UPDATED",
                    entitlement,
                    f"identity={identity.pk} artifact={artifact.pk}",
                )

            if dry_run:
                transaction.set_rollback(True)

        mode = "DRY RUN" if dry_run else "APPLIED"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} — processed={counts['processed']} updated={counts['updated']} "
                f"already_canonical={counts['already_canonical']} "
                f"unresolved={counts['unresolved']} conflicts={counts['conflicts']}"
            )
        )

    def _audit(self, verbose, status, entitlement, detail):
        if verbose:
            self.stdout.write(
                f"[{status}] entitlement={entitlement.pk} "
                f"user={entitlement.user_id} product={entitlement.product_id} — {detail}"
            )
