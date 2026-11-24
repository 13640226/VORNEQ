from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.core.models import UserIdentity
from apps.core.services.identity_lifecycle import provision_verified_identity


class Command(BaseCommand):
    help = "Targeted verified identity backfill; read-only unless --apply is explicit."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        user_id = options["user_id"]
        if user_id <= 0:
            raise CommandError("Invalid user ID")
        with transaction.atomic():
            users = get_user_model().objects.all()
            if options["apply"]:
                users = users.select_for_update()
            user = users.filter(pk=user_id).first()
            if user is None or not user.is_active:
                raise CommandError("Account unavailable")
            if UserIdentity.objects.filter(user=user).exists():
                self.stdout.write("EXISTING_BINDING_UNCHANGED")
                return
            if not user.email or not EmailAddress.objects.filter(user=user, primary=True, verified=True, email__iexact=user.email).exists():
                raise CommandError("Verified primary email required")
            if not options["apply"]:
                self.stdout.write("DRY_RUN_ELIGIBLE_NO_WRITES")
                return
            try:
                _, created = provision_verified_identity(user)
            except PermissionDenied:
                raise CommandError("Account ineligible") from None
            if created:
                record_audit_event(event_name="identity.provisioning.succeeded",
                    actor={"type": "system", "identifier": "core.targeted_backfill"},
                    target={"type": "User", "identifier": user_id},
                    outcome=AuditEvent.Outcome.SUCCEEDED, reason_code="VERIFIED_EMAIL",
                    metadata={"created": True}, retention_class=AuditEvent.RetentionClass.SECURITY)
            self.stdout.write("CREATED" if created else "EXISTING_BINDING_UNCHANGED")
