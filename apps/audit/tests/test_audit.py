from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.audit.models import AuditEvent, AuditEventMutationForbidden
from apps.audit.services import record_audit_event


User = get_user_model()


class AuditEventTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="audit-test-user",
            password="test-pass-123",
        )

    def record_created(self):
        return record_audit_event(
            event_name="verification.request.created",
            actor={"type": "user", "identifier": self.user.pk},
            target={"type": "VerificationRequest", "identifier": 123},
            outcome="created",
            metadata={"new_state": "requested", "request_id": 123},
            reason_code="REQUEST_CREATED",
        )

    def test_record_audit_event_creates_event(self):
        event = self.record_created()
        self.assertIsNotNone(event.event_id)
        self.assertEqual(event.event_name, "verification.request.created")
        self.assertEqual(event.outcome, "created")

    def test_actor_must_have_exact_keys(self):
        with self.assertRaises(ValidationError):
            record_audit_event(
                event_name="verification.request.created",
                actor={
                    "type": "user",
                    "identifier": self.user.pk,
                    "extra": "bad",
                },
                target={"type": "VerificationRequest", "identifier": 123},
                outcome="created",
                metadata={"new_state": "requested", "request_id": 123},
                reason_code="REQUEST_CREATED",
            )

    def test_actor_type_is_bounded(self):
        with self.assertRaises(ValidationError):
            record_audit_event(
                event_name="verification.request.created",
                actor={"type": "admin", "identifier": self.user.pk},
                target={"type": "VerificationRequest", "identifier": 123},
                outcome="created",
                metadata={"new_state": "requested", "request_id": 123},
                reason_code="REQUEST_CREATED",
            )

    def test_metadata_allowlist_rejects_sensitive_key(self):
        with self.assertRaises(ValidationError):
            record_audit_event(
                event_name="verification.request.created",
                actor={"type": "user", "identifier": self.user.pk},
                target={"type": "VerificationRequest", "identifier": 123},
                outcome="created",
                metadata={
                    "new_state": "requested",
                    "request_id": 123,
                    "password": "secret",
                },
                reason_code="REQUEST_CREATED",
            )

    def test_required_metadata_is_enforced(self):
        with self.assertRaises(ValidationError):
            record_audit_event(
                event_name="verification.request.created",
                actor={"type": "user", "identifier": self.user.pk},
                target={"type": "VerificationRequest", "identifier": 123},
                outcome="created",
                metadata={"new_state": "requested"},
                reason_code="REQUEST_CREATED",
            )

    def test_append_only_instance_mutations_are_blocked(self):
        event = self.record_created()
        event.outcome = "failed"
        with self.assertRaises(AuditEventMutationForbidden):
            event.save()
        with self.assertRaises(AuditEventMutationForbidden):
            event.delete()

    def test_append_only_bulk_mutations_are_blocked(self):
        self.record_created()
        with self.assertRaises(AuditEventMutationForbidden):
            AuditEvent.objects.filter(event_name="verification.request.created").update(
                outcome="failed"
            )
        with self.assertRaises(AuditEventMutationForbidden):
            AuditEvent.objects.filter(event_name="verification.request.created").delete()
