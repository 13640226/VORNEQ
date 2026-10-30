"""Draft tenant models for Claim Dossier Batch 001.

No migration or database activation is authorized by this module.
Security-critical membership checks must be enforced by a future service layer.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Organization(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.OneToOneField(
        "core.Identity", on_delete=models.PROTECT, related_name="tenant_organization"
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def clean(self):
        super().clean()
        # Model validation is not a database-level cross-table constraint.
        if self.identity_id and self.identity.kind != "organization":
            raise ValidationError(
                {"identity": "Organization requires an organization-kind Identity."}
            )


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        EDITOR = "editor", "Editor"
        REVIEWER = "reviewer", "Reviewer"
        VIEWER = "viewer", "Viewer"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organization_memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.INVITED
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_invitations_sent",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                condition=Q(status="active"),
                name="core_membership_one_active_per_user_org",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "status", "role"],
                name="core_member_org_status_role_idx",
            )
        ]

    def clean(self):
        super().clean()
        if self.status == self.Status.ACTIVE and self.activated_at is None:
            raise ValidationError({"activated_at": "Active membership requires activation time."})
        if self.status == self.Status.REVOKED and self.revoked_at is None:
            raise ValidationError({"revoked_at": "Revoked membership requires revocation time."})
        if self.status != self.Status.REVOKED and self.revoked_at is not None:
            raise ValidationError({"revoked_at": "Only revoked membership may have revoked_at."})
