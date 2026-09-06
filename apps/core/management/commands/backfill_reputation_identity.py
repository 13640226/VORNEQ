from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import ContextualReputation
from apps.core.services.registry import resolve_identity_for_user


class Command(BaseCommand):
    help = (
        "Backfill ContextualReputation.identity from existing UserIdentity bindings. "
        "Never creates Identity records and never overwrites conflicting canonical state."
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
            help="Persist eligible identity updates.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Process at most this many rows, ordered by primary key.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print one audit line per processed row.",
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

        queryset = ContextualReputation.objects.select_related(
            "user", "identity", "verification_method"
        ).order_by("pk")
        if limit is not None:
            queryset = queryset[:limit]

        counts = {
            "processed": 0,
            "updated": 0,
            "already_set": 0,
            "unresolved": 0,
            "conflicts": 0,
        }

        with transaction.atomic():
            for reputation in queryset:
                counts["processed"] += 1
                resolved_identity = resolve_identity_for_user(reputation.user)

                if reputation.actor_role != ContextualReputation.ActorRole.VERIFIER:
                    counts["conflicts"] += 1
                    self._audit(
                        verbose,
                        "CONFLICT",
                        reputation,
                        "legacy projection has non-verifier actor_role",
                    )
                    continue

                if reputation.identity_id is not None:
                    if resolved_identity is None:
                        counts["conflicts"] += 1
                        self._audit(
                            verbose,
                            "CONFLICT",
                            reputation,
                            "canonical identity is set but UserIdentity cannot be resolved",
                        )
                        continue
                    if reputation.identity_id != resolved_identity.pk:
                        counts["conflicts"] += 1
                        self._audit(
                            verbose,
                            "CONFLICT",
                            reputation,
                            "canonical identity disagrees with current UserIdentity binding",
                        )
                        continue
                    counts["already_set"] += 1
                    self._audit(verbose, "OK", reputation, "already canonical")
                    continue

                if resolved_identity is None:
                    counts["unresolved"] += 1
                    self._audit(
                        verbose,
                        "UNRESOLVED",
                        reputation,
                        "no UserIdentity binding",
                    )
                    continue

                duplicate = ContextualReputation.objects.filter(
                    identity=resolved_identity,
                    actor_role=ContextualReputation.ActorRole.VERIFIER,
                    domain=reputation.domain,
                    verification_method=reputation.verification_method,
                ).exclude(pk=reputation.pk).exists()
                if duplicate:
                    counts["conflicts"] += 1
                    self._audit(
                        verbose,
                        "CONFLICT",
                        reputation,
                        "canonical identity/role/domain/method tuple is already assigned",
                    )
                    continue

                if force:
                    reputation.identity = resolved_identity
                    reputation.save(update_fields=["identity", "updated_at"])

                counts["updated"] += 1
                self._audit(
                    verbose,
                    "WOULD UPDATE" if dry_run else "UPDATED",
                    reputation,
                    f"identity={resolved_identity.pk}",
                )

            if dry_run:
                transaction.set_rollback(True)

        mode = "DRY RUN" if dry_run else "APPLIED"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} — processed={counts['processed']} updated={counts['updated']} "
                f"already_set={counts['already_set']} unresolved={counts['unresolved']} "
                f"conflicts={counts['conflicts']}"
            )
        )

    def _audit(self, verbose, status, reputation, detail):
        if verbose:
            self.stdout.write(
                f"[{status}] reputation={reputation.pk} user={reputation.user_id} "
                f"role={reputation.actor_role} domain={reputation.domain} "
                f"method={reputation.verification_method_id} — {detail}"
            )
