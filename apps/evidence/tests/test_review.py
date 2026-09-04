from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.evidence.models import Claim, ReviewRecord
from apps.evidence.services import (
    EvidenceService,
    ReviewService,
    SnapshotService,
)


User = get_user_model()


class ReviewServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reviewer",
            password="test-pass",
        )

        self.claim = Claim.objects.create(
            claim_text="Test claim for review",
            created_by=self.user,
        )

        self.evidence = EvidenceService.create_with_provenance(
            content="Test evidence",
            content_type="text",
            source_type="human",
            source_ref="tester",
            created_by=self.user,
        )

    def test_claim_initial_state_is_unassessed(self):
        self.assertEqual(
            ReviewService.get_current_state(self.claim),
            "unassessed",
        )

    def test_evidence_initial_state_is_unreviewed(self):
        self.assertEqual(
            ReviewService.get_current_state(self.evidence),
            "unreviewed",
        )

    def test_first_claim_review_uses_unassessed_as_previous_state(self):
        review = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:1",
        )

        self.assertEqual(review.previous_state, "unassessed")
        self.assertEqual(review.new_state, "under_review")

    def test_second_claim_review_uses_latest_state(self):
        first = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:1",
        )

        second = ReviewService.create_review(
            target=self.claim,
            new_state="provisionally_supported",
            reviewer_actor="human:2",
        )

        self.assertEqual(first.previous_state, "unassessed")
        self.assertEqual(first.new_state, "under_review")

        self.assertEqual(second.previous_state, "under_review")
        self.assertEqual(
            second.new_state,
            "provisionally_supported",
        )

        self.assertEqual(
            ReviewService.get_current_state(self.claim),
            "provisionally_supported",
        )

    def test_claim_all_registered_states_are_accepted(self):
        states = [
            "unassessed",
            "under_review",
            "inconclusive",
            "provisionally_supported",
            "provisionally_contradicted",
        ]

        for state in states:
            review = ReviewService.create_review(
                target=self.claim,
                new_state=state,
                reviewer_actor="human:1",
            )

            self.assertEqual(review.new_state, state)

    def test_evidence_all_registered_states_are_accepted(self):
        states = [
            "unreviewed",
            "accepted_source",
            "disputed_source",
            "superseded",
        ]

        for state in states:
            review = ReviewService.create_review(
                target=self.evidence,
                new_state=state,
                reviewer_actor="human:1",
            )

            self.assertEqual(review.new_state, state)

    def test_invalid_claim_state_is_rejected(self):
        with self.assertRaises(ValueError):
            ReviewService.create_review(
                target=self.claim,
                new_state="true",
                reviewer_actor="human:1",
            )

        self.assertEqual(
            ReviewRecord.objects.for_object(self.claim).count(),
            0,
        )

    def test_invalid_evidence_state_is_rejected(self):
        with self.assertRaises(ValueError):
            ReviewService.create_review(
                target=self.evidence,
                new_state="verified",
                reviewer_actor="human:1",
            )

        self.assertEqual(
            ReviewRecord.objects.for_object(self.evidence).count(),
            0,
        )

    def test_review_record_stores_reviewer_actor(self):
        review = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:42",
        )

        self.assertEqual(
            review.reviewer_actor,
            "human:42",
        )

    def test_review_timestamp_is_created(self):
        review = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:1",
        )

        self.assertIsNotNone(review.timestamp)

    def test_review_history_is_append_only(self):
        review = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:1",
        )

        review.new_state = "inconclusive"

        with self.assertRaises(RuntimeError):
            review.save()

        with self.assertRaises(RuntimeError):
            review.delete()

        with self.assertRaises(RuntimeError):
            ReviewRecord.objects.filter(
                pk=review.pk,
            ).update(
                new_state="inconclusive",
            )

        with self.assertRaises(RuntimeError):
            ReviewRecord.objects.filter(
                pk=review.pk,
            ).delete()

    def test_review_queryset_for_object_isolated(self):
        other_claim = Claim.objects.create(
            claim_text="Other claim",
            created_by=self.user,
        )

        expected = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:1",
        )

        ReviewService.create_review(
            target=other_claim,
            new_state="inconclusive",
            reviewer_actor="human:2",
        )

        reviews = ReviewRecord.objects.for_object(
            self.claim,
        )

        self.assertEqual(reviews.count(), 1)
        self.assertEqual(
            reviews.first().pk,
            expected.pk,
        )

    def test_same_state_can_be_recorded_multiple_times(self):
        first = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:1",
        )

        second = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:2",
        )

        self.assertEqual(first.new_state, "under_review")
        self.assertEqual(
            second.previous_state,
            "under_review",
        )
        self.assertEqual(
            second.new_state,
            "under_review",
        )

        self.assertEqual(
            ReviewRecord.objects.for_object(self.claim).count(),
            2,
        )

    def test_empty_reviewer_actor_is_rejected(self):
        with self.assertRaises(ValueError):
            ReviewService.create_review(
                target=self.claim,
                new_state="under_review",
                reviewer_actor="",
            )

    def test_unsaved_target_is_rejected(self):
        unsaved_claim = Claim(
            claim_text="Unsaved claim",
        )

        with self.assertRaises(ValueError):
            ReviewService.create_review(
                target=unsaved_claim,
                new_state="under_review",
                reviewer_actor="human:1",
            )

    def test_claim_review_refreshes_snapshot(self):
        self.assertIsNone(
            SnapshotService.get(self.claim),
        )

        review = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:1",
        )

        snapshot = SnapshotService.get(self.claim)

        self.assertIsNotNone(snapshot)
        self.assertEqual(
            snapshot.current_assessment,
            "under_review",
        )
        self.assertEqual(
            snapshot.derived_from_id,
            review.pk,
        )

        self.assertTrue(
            SnapshotService.verify(self.claim),
        )

    def test_second_review_updates_existing_snapshot(self):
        first = ReviewService.create_review(
            target=self.claim,
            new_state="under_review",
            reviewer_actor="human:1",
        )

        first_snapshot = SnapshotService.get(
            self.claim,
        )

        self.assertIsNotNone(first_snapshot)
        snapshot_pk = first_snapshot.pk

        second = ReviewService.create_review(
            target=self.claim,
            new_state="provisionally_supported",
            reviewer_actor="human:2",
        )

        snapshot = SnapshotService.get(
            self.claim,
        )

        self.assertIsNotNone(snapshot)

        # Snapshot is a cache: the existing row is updated.
        self.assertEqual(
            snapshot.pk,
            snapshot_pk,
        )

        self.assertEqual(
            snapshot.current_assessment,
            "provisionally_supported",
        )

        self.assertEqual(
            snapshot.derived_from_id,
            second.pk,
        )

        self.assertTrue(
            SnapshotService.verify(self.claim),
        )

    def test_evidence_review_does_not_create_claim_snapshot(self):
        ReviewService.create_review(
            target=self.evidence,
            new_state="accepted_source",
            reviewer_actor="human:1",
        )

        self.assertIsNone(
            SnapshotService.get(self.claim),
        )

    def test_claim_history_chain_is_preserved(self):
        states = [
            "under_review",
            "provisionally_supported",
            "inconclusive",
            "provisionally_contradicted",
        ]

        expected_previous = "unassessed"

        for state in states:
            review = ReviewService.create_review(
                target=self.claim,
                new_state=state,
                reviewer_actor="human:1",
            )

            self.assertEqual(
                review.previous_state,
                expected_previous,
            )

            expected_previous = state

        self.assertEqual(
            ReviewService.get_current_state(self.claim),
            "provisionally_contradicted",
        )