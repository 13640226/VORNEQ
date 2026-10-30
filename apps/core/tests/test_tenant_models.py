"""Non-executed unit test specifications for isolated Batch 001."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from apps.core.models import Identity, Membership, Organization


class OrganizationValidationTests(SimpleTestCase):
    def test_organization_identity_kind_is_accepted(self):
        identity = Identity(kind=Identity.Kind.ORGANIZATION, display_name="Example")
        organization = Organization(identity=identity, name="Example", slug="example")
        organization.clean()

    def test_human_identity_kind_is_rejected(self):
        identity = Identity(kind=Identity.Kind.HUMAN, display_name="Person")
        organization = Organization(identity=identity, name="Example", slug="example")
        with self.assertRaises(ValidationError):
            organization.clean()


class MembershipValidationTests(SimpleTestCase):
    def test_active_requires_activation_time(self):
        membership = Membership(role=Membership.Role.EDITOR, status=Membership.Status.ACTIVE)
        with self.assertRaises(ValidationError):
            membership.clean()

    def test_revoked_requires_revocation_time(self):
        membership = Membership(role=Membership.Role.VIEWER, status=Membership.Status.REVOKED)
        with self.assertRaises(ValidationError):
            membership.clean()

    def test_active_with_activation_time_passes_local_validation(self):
        membership = Membership(
            role=Membership.Role.REVIEWER,
            status=Membership.Status.ACTIVE,
            activated_at=timezone.now(),
        )
        membership.clean()

    def test_non_revoked_cannot_have_revocation_time(self):
        membership = Membership(
            role=Membership.Role.OWNER,
            status=Membership.Status.INVITED,
            revoked_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            membership.clean()
