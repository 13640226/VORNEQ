from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase

from apps.audit.models import AuditEvent
from apps.core.models import Identity, UserIdentity


def emit(address):
    email_confirmed.send(sender=EmailAddress, request=None, email_address=address)


class VerifiedLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cil03", email="cil03@example.com")
        self.address = EmailAddress.objects.create(user=self.user, email=self.user.email, primary=True)

    def verify(self):
        self.address.verified = True
        self.address.save(update_fields=["verified"])
        emit(self.address)

    def binding(self):
        return UserIdentity.objects.filter(user=self.user)

    def test_unverified_email_does_not_create_identity(self):
        emit(self.address)
        self.assertFalse(self.binding().exists())

    def test_verified_email_creates_exactly_one_identity(self):
        self.verify()
        self.assertEqual(self.binding().count(), 1)
        self.assertEqual(self.binding().get().identity.kind, Identity.Kind.HUMAN)

    def test_identity_provisioning_is_idempotent(self):
        self.verify()
        pk = self.binding().get().identity_id
        emit(self.address)
        self.assertEqual(self.binding().get().identity_id, pk)
        self.assertEqual(AuditEvent.objects.filter(event_name="identity.provisioning.succeeded").count(), 1)

    def test_inactive_user_no_identity(self):
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        self.verify()
        self.assertFalse(self.binding().exists())

    def test_deactivated_identity_not_reactivated(self):
        self.verify()
        identity = self.binding().get().identity
        identity.is_active = False
        identity.save(update_fields=["is_active"])
        emit(self.address)
        identity.refresh_from_db()
        self.assertFalse(identity.is_active)
        self.assertEqual(self.binding().get().identity_id, identity.pk)

    def test_non_human_identity_type_rejected(self):
        self.verify()
        identity = self.binding().get().identity
        Identity.objects.filter(pk=identity.pk).update(kind=Identity.Kind.AGENT)
        emit(self.address)
        self.assertEqual(self.binding().get().identity.kind, Identity.Kind.AGENT)
        self.assertTrue(AuditEvent.objects.filter(event_name="identity.provisioning.denied").exists())

    def test_no_identity_on_anonymous_access(self):
        self.client.get("/")
        self.assertFalse(self.binding().exists())

    def test_no_identity_on_get_request(self):
        self.client.force_login(self.user)
        self.client.get("/")
        self.assertFalse(self.binding().exists())

    def test_failed_transaction_leaves_no_partial_identity(self):
        before = Identity.objects.count()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.verify()
                raise RuntimeError("rollback")
        self.assertFalse(self.binding().exists())
        self.assertEqual(Identity.objects.count(), before)

    def test_audit_event_recorded_on_success(self):
        self.verify()
        event = AuditEvent.objects.get(event_name="identity.provisioning.succeeded")
        self.assertEqual(event.target, {"type": "User", "identifier": self.user.pk})
        self.assertEqual(event.retention_class, "security")

    def test_audit_event_recorded_on_failure(self):
        with patch("apps.core.identity_signals.provision_verified_identity", side_effect=RuntimeError("secret")):
            with self.assertRaises(PermissionDenied):
                self.verify()
        self.assertTrue(AuditEvent.objects.filter(event_name="identity.provisioning.failed").exists())
        self.assertFalse(self.binding().exists())

    def test_no_pii_in_logs(self):
        with patch("apps.core.identity_signals.provision_verified_identity", side_effect=RuntimeError(self.user.email)):
            with self.assertLogs("apps.core.identity_signals", level="ERROR") as logs:
                with self.assertRaises(PermissionDenied):
                    self.verify()
        self.assertNotIn(self.user.email, str(logs.output))
        self.assertNotIn(self.user.email, str(list(AuditEvent.objects.values())))

    def test_email_change_requires_reverification(self):
        get_user_model().objects.filter(pk=self.user.pk).update(email="new@example.com")
        self.verify()
        self.assertFalse(self.binding().exists())
        new = EmailAddress.objects.create(user=self.user, email="new@example.com", verified=False)
        emit(new)
        self.assertFalse(self.binding().exists())
        self.address.primary = False
        self.address.save(update_fields=["primary"])
        new.primary = new.verified = True
        new.save()
        emit(new)
        self.assertEqual(self.binding().count(), 1)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL row locks required")
class ConcurrentVerificationTests(TransactionTestCase):
    def test_concurrent_verification_creates_single_identity(self):
        user = get_user_model().objects.create_user(username="cil03parallel", email="parallel@example.com")
        address = EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        barrier = Barrier(2)
        def worker():
            try:
                current = EmailAddress.objects.get(pk=address.pk)
                barrier.wait(timeout=10)
                emit(current)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            for future in futures:
                future.result(timeout=30)
        self.assertEqual(UserIdentity.objects.filter(user=user).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(event_name="identity.provisioning.succeeded").count(), 1)
