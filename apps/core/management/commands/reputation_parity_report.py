from django.core.management.base import BaseCommand, CommandError

from apps.core.models import ContextualReputation
from apps.core.services.registry import resolve_identity_for_user


class Command(BaseCommand):
    help = (
        "Report parity between legacy user subjects and canonical Identity subjects "
        "for ContextualReputation. Read-only; makes no changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            help="Check at most this many rows, ordered by primary key.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print one audit line per row.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        verbose = options["verbose"]

        if limit is not None and limit <= 0:
            raise CommandError("--limit must be a positive integer.")

        queryset = ContextualReputation.objects.select_related(
            "user", "identity", "verification_method"
        ).order_by("pk")
        if limit is not None:
            queryset = queryset[:limit]

        counts = {
            "processed": 0,
            "canonical_match": 0,
            "missing_identity": 0,
            "unresolved": 0,
            "identity_mismatch": 0,
            "role_mismatch": 0,
        }

        for reputation in queryset:
            counts["processed"] += 1
            resolved_identity = resolve_identity_for_user(reputation.user)

            if reputation.actor_role != ContextualReputation.ActorRole.VERIFIER:
                counts["role_mismatch"] += 1
                self._audit(
                    verbose,
                    "ROLE MISMATCH",
                    reputation,
                    "legacy verifier projection has a non-verifier actor_role",
                )
                continue

            if reputation.identity_id is None:
                if resolved_identity is None:
                    counts["unresolved"] += 1
                    self._audit(
                        verbose,
                        "UNRESOLVED",
                        reputation,
                        "no canonical identity and no UserIdentity binding",
                    )
                else:
                    counts["missing_identity"] += 1
                    self._audit(
                        verbose,
                        "MISSING",
                        reputation,
                        f"expected identity={resolved_identity.pk}",
                    )
                continue

            if resolved_identity is None:
                counts["identity_mismatch"] += 1
                self._audit(
                    verbose,
                    "MISMATCH",
                    reputation,
                    "canonical identity is set but UserIdentity cannot be resolved",
                )
                continue

            if reputation.identity_id != resolved_identity.pk:
                counts["identity_mismatch"] += 1
                self._audit(
                    verbose,
                    "MISMATCH",
                    reputation,
                    f"actual identity={reputation.identity_id} expected={resolved_identity.pk}",
                )
                continue

            counts["canonical_match"] += 1
            self._audit(verbose, "OK", reputation, "canonical subject matches")

        self.stdout.write(
            self.style.SUCCESS(
                f"PARITY — processed={counts['processed']} "
                f"canonical_match={counts['canonical_match']} "
                f"missing_identity={counts['missing_identity']} "
                f"unresolved={counts['unresolved']} "
                f"identity_mismatch={counts['identity_mismatch']} "
                f"role_mismatch={counts['role_mismatch']}"
            )
        )

    def _audit(self, verbose, status, reputation, detail):
        if verbose:
            self.stdout.write(
                f"[{status}] reputation={reputation.pk} user={reputation.user_id} "
                f"identity={reputation.identity_id} role={reputation.actor_role} "
                f"domain={reputation.domain} method={reputation.verification_method_id} — {detail}"
            )
