"""Disposable-database contracts for audited Marketplace fixture removal."""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.core.models import Artifact, ArtifactBinding
from marketplace.fixture_cleanup import (
    BATCH_ID,
    OWNER_REFERENCE,
    FixtureCleanupRejected,
    _hash_ids,
    cleanup,
)
from marketplace.models import Product, ProductReview


@override_settings(VORNEQ_ENV="development")
class AuditedFixtureCleanupTests(TestCase):
    """Never connects to Render or any actual production datastore."""

    def setUp(self):
        env = patch.dict(
            os.environ,
            {"VORNEQ_FIXTURE_CLEANUP_LOCAL_TEST": "EXPLICIT_TEST_ONLY"},
        )
        env.start()
        self.addCleanup(env.stop)
        User = get_user_model()
        self.benchmark_seller = User.objects.create_user(
            username="vorneq-benchmark-seed"
        )
        self.smoke_seller = User.objects.create_user(
            username="vorneq-inspect-smoke"
        )
        self.benchmark = Product.objects.create(
            seller=self.benchmark_seller,
            title="Benchmark Product",
            slug="vorneq-benchmark-product-000001",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.smoke = Product.objects.create(
            seller=self.smoke_seller,
            title="Smoke Fixture",
            slug="inspect-staging-smoke",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.artifact = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        self.binding = ArtifactBinding.objects.create(
            artifact=self.artifact,
            content_type=ContentType.objects.get_for_model(Product),
            object_id=str(self.smoke.pk),
        )
        self.ids_digest = _hash_ids([self.benchmark, self.smoke])

    def _cleanup(self, apply=False):
        return cleanup(
            apply=apply,
            local_test=True,
            expected_ids_digest=self.ids_digest,
        )

    def test_preview_does_not_mutate_any_rows_or_audit(self):
        preview = self._cleanup()
        self.assertEqual(preview["candidate_count"], 2)
        self.assertTrue(preview["would_delete"])
        self.assertEqual(Product.objects.count(), 2)
        self.assertTrue(Artifact.objects.get(pk=self.artifact.pk).is_active)
        self.assertTrue(ArtifactBinding.objects.filter(pk=self.binding.pk).exists())
        self.assertFalse(AuditEvent.objects.filter(correlation_id=BATCH_ID).exists())

    def test_production_command_does_not_offer_local_test_bypass(self):
        with self.assertRaises(CommandError):
            call_command("marketplace_fixture_cleanup")

    def test_local_test_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {"VORNEQ_FIXTURE_CLEANUP_LOCAL_TEST": ""}):
            with self.assertRaisesRegex(
                FixtureCleanupRejected, "STOP_LOCAL_TEST_ISOLATION"
            ):
                self._cleanup(apply=True)
        self.assertEqual(Product.objects.count(), 2)

    def test_success_is_atomic_and_audited_and_retains_artifact_tombstone(self):
        outcome = self._cleanup(apply=True)
        self.assertEqual(outcome["deleted"], 2)
        self.assertEqual(outcome["audited_events"], 2)
        self.assertEqual(Product.objects.count(), 0)
        self.assertFalse(ArtifactBinding.objects.filter(pk=self.binding.pk).exists())
        self.artifact.refresh_from_db()
        self.assertFalse(self.artifact.is_active)
        events = AuditEvent.objects.filter(correlation_id=BATCH_ID)
        self.assertEqual(events.count(), 2)
        self.assertEqual(
            set(events.values_list("event_name", flat=True)),
            {
                "marketplace.synthetic_cleanup.started",
                "marketplace.synthetic_cleanup.completed",
            },
        )
        self.assertTrue(all(event.retention_class == "security" for event in events))
        self.assertTrue(all(
            event.metadata["authorization_reference"] == OWNER_REFERENCE
            for event in events
        ))

    def test_second_execution_refused_without_new_mutation(self):
        self._cleanup(apply=True)
        with self.assertRaises(FixtureCleanupRejected):
            self._cleanup(apply=True)
        self.assertEqual(AuditEvent.objects.filter(correlation_id=BATCH_ID).count(), 2)

    def test_nonfixture_product_causes_fail_closed(self):
        owner = get_user_model().objects.create_user(username="legitimate-seller")
        Product.objects.create(
            seller=owner, slug="actual-course",
            title="Real Course", status=Product.STATUS_APPROVED, is_published=True,
        )
        with self.assertRaisesRegex(
            FixtureCleanupRejected, "STOP_EXPECTED_PRODUCT_SET_DRIFT"
        ):
            self._cleanup(apply=True)
        self.assertEqual(Product.objects.count(), 3)

    def test_review_blocks_all_cleanup(self):
        reviewer = get_user_model().objects.create_user(username="moderator")
        ProductReview.objects.create(
            product=self.benchmark, moderator=reviewer,
            decision=ProductReview.DECISION_APPROVED,
        )
        with self.assertRaisesRegex(
            FixtureCleanupRejected, "STOP_REVIEW_REFERENCE"
        ):
            self._cleanup(apply=True)
        self.assertEqual(Product.objects.count(), 2)

    def test_missing_artifact_link_blocks_cleanup(self):
        self.binding.delete()
        with self.assertRaisesRegex(
            FixtureCleanupRejected, "STOP_EXPECTED_ONE_ARTIFACT_BINDING"
        ):
            self._cleanup(apply=True)
        self.assertEqual(Product.objects.count(), 2)

    def test_second_audit_event_failure_rolls_back_deletion_and_tombstone(self):
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(kwargs.get("event_name"))
            if len(calls) == 2:
                raise RuntimeError("simulated audit insertion failure")
            return record_audit_event(*args, **kwargs)

        with patch("marketplace.fixture_cleanup.record_audit_event", side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, "simulated audit"):
                self._cleanup(apply=True)
        self.assertEqual(Product.objects.count(), 2)
        self.assertTrue(ArtifactBinding.objects.filter(pk=self.binding.pk).exists())
        self.artifact.refresh_from_db()
        self.assertTrue(self.artifact.is_active)
        self.assertFalse(AuditEvent.objects.filter(correlation_id=BATCH_ID).exists())
