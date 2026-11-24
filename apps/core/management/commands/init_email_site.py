from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = "Inspect site branding; write only with --apply."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        domain = settings.VORNEQ_PUBLIC_DOMAIN
        try:
            URLValidator(schemes=["https"])("https://" + domain)
        except ValidationError:
            raise CommandError("Explicit valid public domain required.") from None
        if not domain or any(c in domain for c in "/:@?# ") or domain == "example.com":
            raise CommandError("Explicit valid public domain required.")
        site = Site.objects.select_for_update().filter(pk=settings.SITE_ID).first()
        if site is None:
            raise CommandError("Configured site does not exist.")
        if site.name == "VORNEQ" and site.domain == domain:
            self.stdout.write("UNCHANGED")
            return
        if not options["apply"]:
            self.stdout.write("DRY_RUN_NO_WRITES")
            return
        site.name = "VORNEQ"
        site.domain = domain
        site.full_clean()
        site.save(update_fields=["name", "domain"])
        self.stdout.write("UPDATED")
