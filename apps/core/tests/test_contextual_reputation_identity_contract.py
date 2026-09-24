from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.core.models import ContextualReputation, Identity
from apps.verification.models import VerificationMethod


User = get_user_model()


class ContextualReputationIdentityContractTests(TestCase):
    def setUp(self):
        self.user_one = User.objects.create_user(username="rep-user-one")
        self.user_two = User.objects.create_user(username="rep-user-two")
        self.identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Canonical Reputation Subject",
        )
        self.method = VerificationMethod.objects.create(
            code="rep-contract-method",
            name="Reputation contract method",
        )

    def test_identity_role_domain_method_is_unique_when_identity_present(self):
        ContextualReputation.objects.create(
            user=self.user_one,
            identity=self.identity,
            actor_role=ContextualReputation.ActorRole.VERIFIER,
            domain="security",
            verification_method=self.method,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ContextualReputation.objects.create(
                    user=self.user_two,
                    identity=self.identity,
                    actor_role=ContextualReputation.ActorRole.VERIFIER,
                    domain="security",
                    verification_method=self.method,
                )

    def test_legacy_rows_without_identity_remain_supported(self):
        first = ContextualReputation.objects.create(
            user=self.user_one,
            domain="security",
            verification_method=self.method,
        )
        second = ContextualReputation.objects.create(
            user=self.user_two,
            domain="security",
            verification_method=self.method,
        )

        self.assertIsNone(first.identity)
        self.assertIsNone(second.identity)
        self.assertEqual(
            first.actor_role,
            ContextualReputation.ActorRole.VERIFIER,
        )
