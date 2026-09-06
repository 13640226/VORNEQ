from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.core.models import ContextualReputation, Identity, UserIdentity
from apps.verification.models import VerificationMethod


User = get_user_model()


class ReputationIdentityBackfillTests(TestCase):
    def setUp(self):
        self.method = VerificationMethod.objects.create(
            code="reputation-backfill-manual",
            name="Reputation backfill manual",
        )
        self.user = User.objects.create_user(username="backfill-user")
        self.identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Backfill User",
        )
        UserIdentity.objects.create(user=self.user, identity=self.identity)
        self.reputation = ContextualReputation.objects.create(
            user=self.user,
            domain="security",
            verification_method=self.method,
        )

    def test_backfill_requires_exactly_one_mode(self):
        with self.assertRaises(CommandError):
            call_command("backfill_reputation_identity")
        with self.assertRaises(CommandError):
            call_command(
                "backfill_reputation_identity",
                dry_run=True,
                force=True,
            )

    def test_dry_run_reports_update_without_mutating(self):
        out = StringIO()
        call_command(
            "backfill_reputation_identity",
            dry_run=True,
            verbose=True,
            stdout=out,
        )

        self.reputation.refresh_from_db()
        self.assertIsNone(self.reputation.identity_id)
        self.assertIn("DRY RUN", out.getvalue())
        self.assertIn("updated=1", out.getvalue())
        self.assertIn("conflicts=0", out.getvalue())

    def test_force_backfills_existing_user_identity(self):
        out = StringIO()
        call_command("backfill_reputation_identity", force=True, stdout=out)

        self.reputation.refresh_from_db()
        self.assertEqual(self.reputation.identity_id, self.identity.pk)
        self.assertEqual(
            self.reputation.actor_role,
            ContextualReputation.ActorRole.VERIFIER,
        )
        self.assertIn("APPLIED", out.getvalue())
        self.assertIn("updated=1", out.getvalue())

    def test_backfill_does_not_create_identity_for_unresolved_user(self):
        unresolved_user = User.objects.create_user(username="unresolved-user")
        unresolved = ContextualReputation.objects.create(
            user=unresolved_user,
            domain="security",
            verification_method=self.method,
        )
        identity_count = Identity.objects.count()
        out = StringIO()

        call_command("backfill_reputation_identity", force=True, stdout=out)

        unresolved.refresh_from_db()
        self.assertIsNone(unresolved.identity_id)
        self.assertEqual(Identity.objects.count(), identity_count)
        self.assertIn("unresolved=1", out.getvalue())

    def test_backfill_fails_closed_on_existing_identity_mismatch(self):
        conflicting_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Conflicting Identity",
        )
        self.reputation.identity = conflicting_identity
        self.reputation.save(update_fields=["identity"])
        out = StringIO()

        call_command(
            "backfill_reputation_identity",
            force=True,
            verbose=True,
            stdout=out,
        )

        self.reputation.refresh_from_db()
        self.assertEqual(self.reputation.identity_id, conflicting_identity.pk)
        self.assertIn("conflicts=1", out.getvalue())
        self.assertIn("CONFLICT", out.getvalue())

    def test_parity_report_tracks_missing_then_matching_identity(self):
        before = StringIO()
        call_command("reputation_parity_report", stdout=before)
        self.assertIn("missing_identity=1", before.getvalue())
        self.assertIn("canonical_match=0", before.getvalue())

        call_command("backfill_reputation_identity", force=True)

        after = StringIO()
        call_command("reputation_parity_report", stdout=after)
        self.assertIn("canonical_match=1", after.getvalue())
        self.assertIn("missing_identity=0", after.getvalue())
        self.assertIn("identity_mismatch=0", after.getvalue())

    def test_parity_report_flags_non_verifier_legacy_role(self):
        self.reputation.actor_role = ContextualReputation.ActorRole.SELLER
        self.reputation.save(update_fields=["actor_role"])
        out = StringIO()

        call_command("reputation_parity_report", stdout=out)

        self.assertIn("role_mismatch=1", out.getvalue())
        self.assertIn("canonical_match=0", out.getvalue())
