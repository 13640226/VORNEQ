from django.test import TestCase

from apps.evidence.domain.digests import (
    DIGEST_VERSION,
    snapshot_digest,
)
from apps.evidence.models import (
    AssessmentSnapshot,
    Claim,
    ReviewRecord,
)
from apps.evidence.services import (
    ReviewService,
    SnapshotService,
)


class SnapshotServiceTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(
            claim_text="Snapshot test claim",
            scope="E0 snapshot tests",
        )

    def create_review(
        self,
        *,
        state="under_review",
        reviewer="test-reviewer",
        notes="",
    ):
        return ReviewService.create_review(
            target=self.claim,
            new_state=state,
            reviewer_actor=reviewer,
            notes=notes,
        )

    def test_get_returns_none_when_snapshot_does_not_exist(self):
        snapshot = SnapshotService.get(
            self.claim
        )

        self.assertIsNone(snapshot)

    def test_verify_returns_true_when_neither_review_nor_snapshot_exists(self):
        self.assertTrue(
            SnapshotService.verify(
                self.claim
            )
        )

    def test_refresh_returns_none_without_review_history(self):
        snapshot = SnapshotService.refresh(
            self.claim
        )

        self.assertIsNone(snapshot)

        self.assertFalse(
            AssessmentSnapshot.objects.filter(
                claim=self.claim
            ).exists()
        )

    def test_refresh_rejects_unsaved_claim(self):
        unsaved_claim = Claim(
            claim_text="Unsaved claim",
        )

        with self.assertRaises(ValueError):
            SnapshotService.refresh(
                unsaved_claim
            )

    def test_review_creation_creates_snapshot_for_claim(self):
        review = self.create_review()

        snapshot = SnapshotService.get(
            self.claim
        )

        self.assertIsNotNone(snapshot)

        self.assertEqual(
            snapshot.current_assessment,
            review.new_state,
        )

        self.assertEqual(
            snapshot.derived_from,
            review,
        )

        self.assertEqual(
            snapshot.snapshot_at,
            review.timestamp,
        )

    def test_snapshot_digest_matches_canonical_digest(self):
        review = self.create_review()

        snapshot = SnapshotService.get(
            self.claim
        )

        expected_digest = snapshot_digest(
            claim_id=self.claim.pk,
            review_id=review.pk,
            state=review.new_state,
            timestamp=review.timestamp,
            digest_version=DIGEST_VERSION,
        )

        self.assertEqual(
            snapshot.digest,
            expected_digest,
        )

        self.assertEqual(
            snapshot.digest_version,
            DIGEST_VERSION,
        )

        self.assertEqual(
            len(snapshot.digest),
            64,
        )

    def test_verify_returns_true_for_valid_snapshot(self):
        self.create_review()

        self.assertTrue(
            SnapshotService.verify(
                self.claim
            )
        )

    def test_refresh_is_idempotent(self):
        self.create_review()

        first_snapshot = SnapshotService.refresh(
            self.claim
        )

        second_snapshot = SnapshotService.refresh(
            self.claim
        )

        self.assertEqual(
            first_snapshot.pk,
            second_snapshot.pk,
        )

        self.assertEqual(
            AssessmentSnapshot.objects.filter(
                claim=self.claim
            ).count(),
            1,
        )

    def test_rebuild_delegates_to_canonical_history(self):
        review = self.create_review()

        snapshot = SnapshotService.rebuild(
            self.claim
        )

        self.assertIsNotNone(snapshot)

        self.assertEqual(
            snapshot.current_assessment,
            review.new_state,
        )

        self.assertEqual(
            snapshot.derived_from,
            review,
        )

    def test_second_review_updates_existing_snapshot(self):
        first_review = self.create_review(
            state="under_review",
            reviewer="reviewer-1",
        )

        first_snapshot = SnapshotService.get(
            self.claim
        )

        first_snapshot_pk = first_snapshot.pk

        second_review = self.create_review(
            state="provisionally_supported",
            reviewer="reviewer-2",
        )

        second_snapshot = SnapshotService.get(
            self.claim
        )

        self.assertEqual(
            second_snapshot.pk,
            first_snapshot_pk,
        )

        self.assertEqual(
            second_snapshot.current_assessment,
            second_review.new_state,
        )

        self.assertEqual(
            second_snapshot.derived_from,
            second_review,
        )

        self.assertNotEqual(
            second_snapshot.derived_from,
            first_review,
        )

        self.assertEqual(
            AssessmentSnapshot.objects.filter(
                claim=self.claim
            ).count(),
            1,
        )

    def test_latest_review_is_authoritative(self):
        first_review = self.create_review(
            state="under_review",
            reviewer="reviewer-1",
        )

        second_review = self.create_review(
            state="provisionally_supported",
            reviewer="reviewer-2",
        )

        snapshot = SnapshotService.refresh(
            self.claim
        )

        self.assertEqual(
            snapshot.derived_from_id,
            second_review.pk,
        )

        self.assertEqual(
            snapshot.current_assessment,
            second_review.new_state,
        )

        self.assertNotEqual(
            snapshot.derived_from_id,
            first_review.pk,
        )

    def test_verify_detects_tampered_digest(self):
        self.create_review()

        snapshot = SnapshotService.get(
            self.claim
        )

        AssessmentSnapshot.objects.filter(
            pk=snapshot.pk
        ).update(
            digest="0" * 64
        )

        self.assertFalse(
            SnapshotService.verify(
                self.claim
            )
        )

    def test_verify_detects_wrong_assessment(self):
        self.create_review()

        snapshot = SnapshotService.get(
            self.claim
        )

        AssessmentSnapshot.objects.filter(
            pk=snapshot.pk
        ).update(
            current_assessment="invalid-state"
        )

        self.assertFalse(
            SnapshotService.verify(
                self.claim
            )
        )

    def test_verify_detects_wrong_digest_version(self):
        self.create_review()

        snapshot = SnapshotService.get(
            self.claim
        )

        AssessmentSnapshot.objects.filter(
            pk=snapshot.pk
        ).update(
            digest_version="invalid-version"
        )

        self.assertFalse(
            SnapshotService.verify(
                self.claim
            )
        )

    def test_verify_detects_missing_snapshot_when_review_exists(self):
        self.create_review()

        AssessmentSnapshot.objects.filter(
            claim=self.claim
        ).delete()

        self.assertTrue(
            ReviewRecord.objects
            .for_object(self.claim)
            .exists()
        )

        self.assertFalse(
            SnapshotService.verify(
                self.claim
            )
        )

    def test_rebuild_restores_missing_snapshot(self):
        review = self.create_review()

        AssessmentSnapshot.objects.filter(
            claim=self.claim
        ).delete()

        self.assertIsNone(
            SnapshotService.get(
                self.claim
            )
        )

        rebuilt = SnapshotService.rebuild(
            self.claim
        )

        self.assertIsNotNone(rebuilt)

        self.assertEqual(
            rebuilt.derived_from,
            review,
        )

        self.assertEqual(
            rebuilt.current_assessment,
            review.new_state,
        )

        self.assertTrue(
            SnapshotService.verify(
                self.claim
            )
        )

    def test_refresh_repairs_stale_snapshot(self):
        review = self.create_review()

        snapshot = SnapshotService.get(
            self.claim
        )

        AssessmentSnapshot.objects.filter(
            pk=snapshot.pk
        ).update(
            current_assessment="stale-state",
            digest="f" * 64,
        )

        self.assertFalse(
            SnapshotService.verify(
                self.claim
            )
        )

        refreshed = SnapshotService.refresh(
            self.claim
        )

        self.assertEqual(
            refreshed.current_assessment,
            review.new_state,
        )

        self.assertEqual(
            refreshed.derived_from,
            review,
        )

        self.assertTrue(
            SnapshotService.verify(
                self.claim
            )
        )