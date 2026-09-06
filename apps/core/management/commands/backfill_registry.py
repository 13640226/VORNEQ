from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.services.registry import register_artifact, register_user_identity
from marketplace.models import Product


class Command(BaseCommand):
    help = (
        "Idempotently register existing Marketplace Products and Django Users "
        "in the Core Artifact/Identity registries. LibraryItem is intentionally excluded."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate the backfill and roll back all writes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        User = get_user_model()

        product_created = 0
        product_existing = 0
        identity_created = 0
        identity_existing = 0

        with transaction.atomic():
            for product in Product.objects.order_by("pk").iterator():
                _, created = register_artifact(product)
                if created:
                    product_created += 1
                else:
                    product_existing += 1

            for user in User.objects.order_by("pk").iterator():
                _, created = register_user_identity(user)
                if created:
                    identity_created += 1
                else:
                    identity_existing += 1

            if dry_run:
                transaction.set_rollback(True)

        prefix = "DRY RUN — " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Products: {product_created} created, {product_existing} existing; "
                f"Users: {identity_created} created, {identity_existing} existing."
            )
        )
