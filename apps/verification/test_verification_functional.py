"""Functional view-to-service tests with isolated mocks.

These tests assert state transitions through the HTTP view layer, but do not
establish persistence or PostgreSQL/SQLite integration correctness.
"""
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from .models import VerificationRequest


class VerificationFunctionalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="verification-pilot", password="test-password"
        )
        self.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="verification",
                codename__in=[
                    "add_verificationrequest",
                    "change_verificationrequest",
                    "add_verificationresult",
                ],
            )
        )
        self.client.force_login(self.user)

    @patch("apps.verification.views.request_verification")
    @patch("apps.verification.views.get_object_or_404")
    @patch("apps.verification.views.ContentType.objects.get_for_id")
    @patch("apps.verification.views.VerificationRequestForm")
    def test_request_verification_creates_record(self, form_cls, get_ct, get_obj, service):
        form = form_cls.return_value
        form.is_valid.return_value = True
        form.cleaned_data = {
            "artifact_content_type": SimpleNamespace(pk=1),
            "artifact_object_id": "1",
            "claim": object(),
            "method": object(),
        }
        get_ct.return_value.model_class.return_value = object()
        service.return_value = SimpleNamespace(pk=42, status="requested")
        response = self.client.post(reverse("verification:create"), data={})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(service.return_value.status, "requested")
        service.assert_called_once()

    @patch("apps.verification.views.start_verification")
    @patch("apps.verification.views.get_object_or_404")
    def test_start_verification_changes_status(self, get_obj, service):
        obj = SimpleNamespace(pk=1, requested_by_id=self.user.pk, status="requested")
        get_obj.return_value = obj
        def transition(**kwargs):
            obj.status = "in_progress"
            return obj
        service.side_effect = transition
        response = self.client.post(reverse("verification:start", args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(obj.status, "in_progress")

    @patch("apps.verification.views.submit_verification_result")
    @patch("apps.verification.views.get_object_or_404")
    @patch("apps.verification.views.VerificationResultForm")
    def test_submit_result_completes_verification(self, form_cls, get_obj, service):
        obj = SimpleNamespace(pk=1, requested_by_id=self.user.pk, status="in_progress")
        get_obj.return_value = obj
        form = form_cls.return_value
        form.is_valid.return_value = True
        form.cleaned_data = {"outcome": "pass", "reported_confidence": 80, "summary": "OK"}
        service.side_effect = lambda **kwargs: setattr(obj, "status", "completed")
        response = self.client.post(reverse("verification:submit", args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(obj.status, "completed")

    @patch("apps.verification.views.cancel_verification")
    @patch("apps.verification.views.get_object_or_404")
    def test_cancel_verification_stops_process(self, get_obj, service):
        obj = SimpleNamespace(pk=1, requested_by_id=self.user.pk, status="in_progress")
        get_obj.return_value = obj
        service.side_effect = lambda **kwargs: setattr(obj, "status", "cancelled")
        response = self.client.post(reverse("verification:cancel", args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(obj.status, "cancelled")

    @patch("apps.verification.views.get_object_or_404")
    def test_unauthorized_user_cannot_start(self, get_obj):
        other = get_user_model().objects.create_user(
            username="verification-other", password="test-password"
        )
        other.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="verification",
                codename="change_verificationrequest",
            )
        )
        self.client.force_login(other)
        get_obj.return_value = SimpleNamespace(pk=1, requested_by_id=self.user.pk)
        response = self.client.post(reverse("verification:start", args=[1]))
        self.assertEqual(response.status_code, 403)
