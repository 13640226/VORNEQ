import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from apps.core.services.context import get_context_view, resolve_artifact_from_input
from apps.core.services.registry import register_artifact
from marketplace.models import Product


SMOKE_USERNAME = "vorneq-inspect-smoke"
SMOKE_SLUG = "inspect-staging-smoke"
SMOKE_TITLE = "Inspect Staging Smoke Product"


class Command(BaseCommand):
    help = "Run an idempotent Inspect Context V1 smoke test against staging data."

    def handle(self, *args, **options):
        if os.environ.get("VORNEQ_ALLOW_INSPECT_STAGING_SMOKE", "").lower() != "yes":
            raise CommandError(
                "Refusing to run: VORNEQ_ALLOW_INSPECT_STAGING_SMOKE must be set to 'yes'."
            )

        User = get_user_model()
        user, user_created = User.objects.get_or_create(username=SMOKE_USERNAME)
        if user_created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        product, _ = Product.objects.update_or_create(
            slug=SMOKE_SLUG,
            defaults={
                "seller": user,
                "title": SMOKE_TITLE,
                "short_description": "Operational smoke fixture for Inspect Context V1.",
                "status": Product.STATUS_APPROVED,
                "is_published": True,
            },
        )

        artifact, _ = register_artifact(product, created_by=user)

        product_path = product.get_absolute_url()
        full_url = f"https://staging.example.test{product_path}"
        inputs = {
            "title": product.title,
            "slug": product.slug,
            "url": full_url,
            "uuid": str(artifact.id),
        }

        for label, value in inputs.items():
            resolved = resolve_artifact_from_input(value)
            if resolved != artifact:
                resolved_id = getattr(resolved, "id", None)
                raise CommandError(
                    f"FAIL: {label} input resolved to {resolved_id!s}, expected {artifact.id}."
                )
            self.stdout.write(f"PASS: {label} input resolved to {artifact.id}")

        context = get_context_view(artifact.id, language="en")
        if context.get("artifact") != artifact:
            raise CommandError("FAIL: Context projection did not return the expected Artifact.")
        if context.get("source", {}).get("title") != product.title:
            raise CommandError("FAIL: Context projection did not return the expected source title.")

        canonical_path = reverse("context_view", kwargs={"artifact_id": artifact.id})
        if str(artifact.id) not in canonical_path:
            raise CommandError("FAIL: Canonical Context URL does not contain the Artifact UUID.")

        self.stdout.write(self.style.SUCCESS("PASS: Inspect Context V1 staging smoke test passed."))
        self.stdout.write(f"Product ID: {product.id}")
        self.stdout.write(f"Artifact ID: {artifact.id}")
        self.stdout.write(f"Canonical URL: {canonical_path}")
