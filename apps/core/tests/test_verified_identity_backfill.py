from io import StringIO
from unittest.mock import patch
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from apps.core.models import Identity, UserIdentity
from apps.audit.models import AuditEvent


class TargetedBackfillTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="backfill", email="backfill@example.com")
        self.address = EmailAddress.objects.create(user=self.user, email=self.user.email, primary=True, verified=True)

    def run_command(self, *args):
        out = StringIO()
        call_command("backfill_verified_identity", "--user-id", str(self.user.pk), *args, stdout=out)
        return out.getvalue()

    def test_default_read_only(self):
        self.assertIn("DRY_RUN", self.run_command())
        self.assertFalse(UserIdentity.objects.filter(user=self.user).exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_apply_idempotent_and_targeted(self):
        other = get_user_model().objects.create_user(username="other", email="other@example.com")
        EmailAddress.objects.create(user=other, email=other.email, primary=True, verified=True)
        self.assertIn("CREATED", self.run_command("--apply"))
        self.assertIn("UNCHANGED", self.run_command("--apply"))
        self.assertEqual(UserIdentity.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(event_name="identity.provisioning.succeeded").count(), 1)

    def test_unverified_denied(self):
        self.address.verified = False
        self.address.save()
        with self.assertRaises(CommandError):
            self.run_command("--apply")
        self.assertFalse(UserIdentity.objects.exists())

    def test_inactive_account_denied(self):
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(CommandError):
            self.run_command("--apply")
        self.assertFalse(UserIdentity.objects.exists())

    def test_inactive_binding_unchanged(self):
        identity = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name="Existing", is_active=False)
        UserIdentity.objects.create(user=self.user, identity=identity)
        self.assertIn("UNCHANGED", self.run_command("--apply"))
        identity.refresh_from_db()
        self.assertFalse(identity.is_active)
        self.assertEqual(UserIdentity.objects.get(user=self.user).identity_id, identity.pk)

    def test_audit_failure_rolls_back(self):
        with patch("apps.core.management.commands.backfill_verified_identity.record_audit_event", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.run_command("--apply")
        self.assertFalse(UserIdentity.objects.exists())
