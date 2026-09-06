from django.test import TestCase

from apps.evidence.models import Claim, Critique, Dispute, ReviewRecord
from apps.evidence.services import DisputeService


class DisputeWorkflowTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(claim_text="A test claim")
        self.critique = Critique.objects.create(
            claim=self.claim,
            category=Critique.Category.METHOD,
            body="The method should be contested.",
        )

    def test_open_dispute_creates_canonical_review_history(self):
        dispute = DisputeService.open_dispute(
            critique=self.critique,
            reviewer_actor="test-reviewer",
        )

        self.assertEqual(DisputeService.get_state(dispute), "open")
        reviews = ReviewRecord.objects.for_object(dispute)
        self.assertEqual(reviews.count(), 1)
        self.assertEqual(reviews.first().new_state, "open")
        self.assertEqual(dispute.target, self.claim)

    def test_valid_lifecycle(self):
        dispute = DisputeService.open_dispute(
            critique=self.critique,
            reviewer_actor="test-reviewer",
        )
        DisputeService.transition(
            dispute=dispute,
            new_state="under_review",
            reviewer_actor="reviewer-2",
        )
        DisputeService.transition(
            dispute=dispute,
            new_state="resolved",
            reviewer_actor="reviewer-2",
            notes="Resolution recorded.",
        )

        self.assertEqual(DisputeService.get_state(dispute), "resolved")
        self.assertEqual(ReviewRecord.objects.for_object(dispute).count(), 3)

    def test_invalid_transition_is_rejected(self):
        dispute = DisputeService.open_dispute(
            critique=self.critique,
            reviewer_actor="test-reviewer",
        )
        with self.assertRaises(ValueError):
            DisputeService.transition(
                dispute=dispute,
                new_state="resolved",
                reviewer_actor="reviewer-2",
            )

    def test_terminal_state_cannot_transition(self):
        dispute = DisputeService.open_dispute(
            critique=self.critique,
            reviewer_actor="test-reviewer",
        )
        DisputeService.transition(
            dispute=dispute,
            new_state="withdrawn",
            reviewer_actor="test-reviewer",
        )
        with self.assertRaises(ValueError):
            DisputeService.transition(
                dispute=dispute,
                new_state="under_review",
                reviewer_actor="reviewer-2",
            )

    def test_dispute_is_immutable(self):
        dispute = DisputeService.open_dispute(
            critique=self.critique,
            reviewer_actor="test-reviewer",
        )
        with self.assertRaises(RuntimeError):
            dispute.save()
        with self.assertRaises(RuntimeError):
            dispute.delete()

    def test_reply_critique_cannot_open_dispute(self):
        reply = Critique.objects.create(
            claim=self.claim,
            parent=self.critique,
            category=Critique.Category.OTHER,
            body="Reply",
        )
        with self.assertRaises(ValueError):
            DisputeService.open_dispute(
                critique=reply,
                reviewer_actor="test-reviewer",
            )
