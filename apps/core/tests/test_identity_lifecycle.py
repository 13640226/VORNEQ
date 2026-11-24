from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.core.models import Identity, UserIdentity
from apps.core.services.identity_lifecycle import provision_verified_identity


class IdentityLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lifecycle", email="lifecycle@example.com")

    def verify(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, primary=True, verified=True)

    def test_unverified_denied(self):
        with self.assertRaises(PermissionDenied):
            provision_verified_identity(self.user)
        self.assertFalse(UserIdentity.objects.filter(user=self.user).exists())

    def test_verified_idempotent(self):
        self.verify()
        first, created = provision_verified_identity(self.user)
        self.assertTrue(created)
        second, created = provision_verified_identity(self.user)
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.kind, Identity.Kind.HUMAN)

    def test_inactive_identity_not_replaced(self):
        self.verify()
        identity, _ = provision_verified_identity(self.user)
        identity.is_active = False
        identity.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            provision_verified_identity(self.user)
        self.assertEqual(UserIdentity.objects.get(user=self.user).identity_id, identity.pk)

    def test_inactive_account_denied(self):
        self.verify()
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            provision_verified_identity(self.user)
        self.assertFalse(UserIdentity.objects.filter(user=self.user).exists())


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connection, connections
from django.test import TransactionTestCase
from unittest import skipUnless


@skipUnless(connection.vendor == "postgresql", "PostgreSQL row locks required")
class IdentityConcurrencyTests(TransactionTestCase):
    def test_parallel_provisioning(self):
        user = get_user_model().objects.create_user(username="parallel", email="parallel@example.com")
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        barrier = Barrier(2)
        def worker():
            try:
                account = get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                identity, created = provision_verified_identity(account)
                return identity.pk, created
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(UserIdentity.objects.filter(user=user).count(), 1)
