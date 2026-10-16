from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import ArtifactBinding, Entitlement, UserIdentity


def _canonical_state(entitlement):
    has_identity = entitlement.identity_id is not None
    has_artifact = entitlement.artifact_id is not None
    if has_identity and has_artifact:
        return "canonical_complete"
    if not has_identity and not has_artifact:
        return "legacy_only"
    return "partial_canonical"


def _authorization_allowed(entitlement, resolved_identity_id, resolved_artifact_id):
    """Mirror the current dual-read authorization policy without per-row registry queries."""
    if not entitlement.is_valid():
        return False

    state = _canonical_state(entitlement)
    if state == "partial_canonical":
        return False
    if state == "legacy_only":
        return True
    if resolved_identity_id is None or resolved_artifact_id is None:
        return False
    return (
        entitlement.identity_id == resolved_identity_id
        and entitlement.artifact_id == resolved_artifact_id
    )


class Command(BaseCommand):
    help = "Report Entitlement canonical/legacy parity and deprecation readiness (read-only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show one audit line per processed Entitlement.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Process at most this many Entitlements, ordered by primary key.",
        )

    def handle(self, *args, **options):
        verbose = options["verbose"]
        limit = options["limit"]
        if limit is not None and limit <= 0:
            raise CommandError("--limit must be a positive integer.")

        queryset = Entitlement.objects.select_related(
            "user", "product", "identity", "artifact"
        ).order_by("pk")
        if limit is not None:
            queryset = queryset[:limit]
        entitlements = list(queryset)

        user_ids = {entitlement.user_id for entitlement in entitlements}
        product_ids = {str(entitlement.product_id) for entitlement in entitlements}

        identity_by_user_id = dict(
            UserIdentity.objects.filter(user_id__in=user_ids).values_list(
                "user_id", "identity_id"
            )
        )

        product_model = Entitlement._meta.get_field("product").remote_field.model
        product_content_type = ContentType.objects.get_for_model(
            product_model,
            for_concrete_model=False,
        )
        artifact_by_product_id = dict(
            ArtifactBinding.objects.filter(
                content_type=product_content_type,
                object_id__in=product_ids,
            ).values_list("object_id", "artifact_id")
        )

        stats = {
            "processed": 0,
            "canonical_complete": 0,
            "legacy_only": 0,
            "partial_canonical": 0,
            "registry_resolved": 0,
            "registry_unresolved": 0,
            "canonical_match": 0,
            "canonical_mismatch": 0,
            "authorization_allowed": 0,
            "authorization_denied": 0,
        }

        for entitlement in entitlements:
            stats["processed"] += 1
            state = _canonical_state(entitlement)
            stats[state] += 1

            resolved_identity_id = identity_by_user_id.get(entitlement.user_id)
            resolved_artifact_id = artifact_by_product_id.get(str(entitlement.product_id))
            registry_resolved = (
                resolved_identity_id is not None and resolved_artifact_id is not None
            )
            stats["registry_resolved" if registry_resolved else "registry_unresolved"] += 1

            canonical_status = "not_applicable"
            if state == "canonical_complete" and registry_resolved:
                if (
                    entitlement.identity_id == resolved_identity_id
                    and entitlement.artifact_id == resolved_artifact_id
                ):
                    stats["canonical_match"] += 1
                    canonical_status = "match"
                else:
                    stats["canonical_mismatch"] += 1
                    canonical_status = "mismatch"

            allowed = _authorization_allowed(
                entitlement,
                resolved_identity_id,
                resolved_artifact_id,
            )
            stats["authorization_allowed" if allowed else "authorization_denied"] += 1

            if verbose:
                self.stdout.write(
                    f"entitlement={entitlement.pk} state={state} "
                    f"registry={'resolved' if registry_resolved else 'unresolved'} "
                    f"canonical={canonical_status} "
                    f"authorization={'allowed' if allowed else 'denied'}"
                )

        conflicts = stats["partial_canonical"] + stats["canonical_mismatch"]
        self.stdout.write("ENTITLEMENT PARITY REPORT")
        self.stdout.write(f"processed={stats['processed']}")
        self.stdout.write(f"canonical_complete={stats['canonical_complete']}")
        self.stdout.write(f"legacy_only={stats['legacy_only']}")
        self.stdout.write(f"partial_canonical={stats['partial_canonical']}")
        self.stdout.write(f"registry_resolved={stats['registry_resolved']}")
        self.stdout.write(f"registry_unresolved={stats['registry_unresolved']}")
        self.stdout.write(f"canonical_match={stats['canonical_match']}")
        self.stdout.write(f"canonical_mismatch={stats['canonical_mismatch']}")
        self.stdout.write(f"conflicts={conflicts}")
        self.stdout.write(f"authorization_allowed={stats['authorization_allowed']}")
        self.stdout.write(f"authorization_denied={stats['authorization_denied']}")
