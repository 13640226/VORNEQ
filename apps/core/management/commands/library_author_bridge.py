from django.core.management.base import BaseCommand, CommandError

from apps.core.models import ArtifactIdentityRole, Identity
from apps.core.services.library_bridge import map_library_author_to_identity
from apps.core.services.registry import resolve_artifact
from library.models import LibraryItem


class Command(BaseCommand):
    help = (
        "Report LibraryItems that do not have an explicit Registry author role, "
        "or explicitly map one LibraryItem to an existing Identity. "
        "The legacy author string is never used for inference."
    )

    def add_arguments(self, parser):
        parser.add_argument("--library-item-id", type=int)
        parser.add_argument("--identity-id")

    def handle(self, *args, **options):
        item_id = options.get("library_item_id")
        identity_id = options.get("identity_id")

        if bool(item_id) != bool(identity_id):
            raise CommandError(
                "--library-item-id and --identity-id must be supplied together."
            )

        if item_id and identity_id:
            try:
                item = LibraryItem.objects.get(pk=item_id)
            except LibraryItem.DoesNotExist as exc:
                raise CommandError("LibraryItem does not exist.") from exc
            try:
                identity = Identity.objects.get(pk=identity_id)
            except (Identity.DoesNotExist, ValueError) as exc:
                raise CommandError("Identity does not exist.") from exc

            role, created = map_library_author_to_identity(item, identity)
            status = "created" if created else "existing"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Author mapping {status}: LibraryItem {item.pk} -> Identity {identity.pk} "
                    f"(role {role.pk})."
                )
            )
            return

        unresolved = 0
        for item in LibraryItem.objects.exclude(author="").order_by("pk").iterator():
            artifact = resolve_artifact(item)
            has_author_role = False
            if artifact is not None:
                has_author_role = ArtifactIdentityRole.objects.filter(
                    artifact=artifact,
                    role=ArtifactIdentityRole.Role.AUTHOR,
                ).exists()
            if not has_author_role:
                unresolved += 1
                artifact_ref = str(artifact.pk) if artifact else "unregistered"
                self.stdout.write(
                    f"LibraryItem {item.pk} | artifact={artifact_ref} | author_text={item.author!r}"
                )

        self.stdout.write(
            self.style.WARNING(
                f"Unmapped LibraryItems with non-empty legacy author text: {unresolved}. "
                "No identity suggestions or automatic mappings were made."
            )
        )
