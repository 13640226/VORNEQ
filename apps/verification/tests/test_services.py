from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.evidence.models import Claim, Evidence, EvidenceRelation, ReviewRecord
from apps.verification.models import VerificationEvidence, VerificationMethod, VerificationRequest
from apps.verification.services import (
    DuplicateActiveVerification,
    InvalidVerificationTransition,
    VerificationAuthorizationError,
    cancel_verification,
    request_verification,
    start_verification,
    submit_verification_result,
)
from marketplace.models import Product


User = get_user_model()


class VerificationServiceTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff-verifier",
            password="test-pass-123",
            is_staff=True,
        )
        self.regular = User.objects.create_user(
            username="regular-user",
            password="test-pass-123",
        )
        self.product = Product.objects.create(
            seller=self.staff,
            title="Service Test Product",
        )
        self.claim = Claim.objects.create(
            claim_text="The product satisfies the verification claim.",
            created_by=self.staff,
        )
        self.method = VerificationMethod.objects.create(
            code="manual-service-review",
            name="Manual service review",
        )
        self.evidence = Evidence.objects.create(
            content="Observed supporting material.",
            content_type=Evidence.ContentType.TEXT,
            integrity_digest="1" * 64,
            created_by=self.staff,
        )
        self.relation = EvidenceRelation.objects.create(
            claim=self.claim,
            evidence=self.evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            created_by=self.staff,
        )

    def make_request(self):
        return request_verification(
            artifact=self.product,
            claim=self.claim,
            method=self.method,
            requested_by=self.staff,
        )

    def test_request_requires_authorization(self):
        with self.assertRaises(VerificationAuthorizationError):
            request_verification(
                artifact=self.product,
                claim=self.claim,
                method=self.method,
                requested_by=self.regular,
            )

    def test_duplicate_active_request_is_rejected_but_history_can_repeat(self):
        first = self.make_request()
        with self.assertRaises(DuplicateActiveVerification):
            self.make_request()

        cancel_verification(verification_request=first, actor=self.staff)
        second = self.make_request()
        self.assertNotEqual(first.pk, second.pk)

    def test_start_and_submit_complete_request_atomically(self):
        request = self.make_request()
        started = start_verification(verification_request=request, actor=self.staff)
        result = submit_verification_result(
            verification_request=started,
            verifier=self.staff,
            outcome="pass",
            reported_confidence=90,
            summary="Supported by canonical evidence.",
            evidence_links=[
                {
                    "evidence_relation": self.relation,
                    "visibility": VerificationEvidence.Visibility.PUBLIC,
                }
            ],
        )

        started.refresh_from_db()
        self.assertEqual(started.status, VerificationRequest.Status.COMPLETED)
        self.assertEqual(result.evidence_links.count(), 1)
        self.assertEqual(result.evidence_links.get().evidence_relation, self.relation)

    def test_submit_before_start_is_rejected(self):
        request = self.make_request()
        with self.assertRaises(InvalidVerificationTransition):
            submit_verification_result(
                verification_request=request,
                verifier=self.staff,
                outcome="pass",
                reported_confidence=80,
            )

    def test_terminal_request_cannot_restart(self):
        request = self.make_request()
        cancel_verification(verification_request=request, actor=self.staff)
        with self.assertRaises(InvalidVerificationTransition):
            start_verification(verification_request=request, actor=self.staff)

    def test_transitions_are_recorded_in_append_only_review_history(self):
        request = self.make_request()
        started = start_verification(verification_request=request, actor=self.staff)
        submit_verification_result(
            verification_request=started,
            verifier=self.staff,
            outcome="inconclusive",
            reported_confidence=40,
        )

        records = ReviewRecord.objects.for_target(request).order_by("timestamp", "id")
        self.assertEqual(
            list(records.values_list("new_state", flat=True)),
            ["requested", "in_progress", "completed"],
        )
