"""Isolated view contract tests; no operational database connections."""
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from django.urls import resolve, reverse
from django.contrib.auth.models import AnonymousUser
from . import views


class VerificationRoutingTests(SimpleTestCase):
    def test_create_route(self):
        self.assertIs(resolve(reverse("verification:create")).func.view_class, views.VerificationCreateView)

    def test_start_route(self):
        self.assertIs(resolve(reverse("verification:start", args=[1])).func.view_class, views.VerificationStartView)

    def test_submit_route(self):
        self.assertIs(resolve(reverse("verification:submit", args=[1])).func.view_class, views.VerificationSubmitView)

    def test_cancel_route(self):
        self.assertIs(resolve(reverse("verification:cancel", args=[1])).func.view_class, views.VerificationCancelView)

    def test_fail_route(self):
        self.assertIs(resolve(reverse("verification:fail", args=[1])).func.view_class, views.VerificationFailView)

    def test_anonymous_user_cannot_access_list(self):
        request = RequestFactory().get("/api/verification/manage/")
        request.user = AnonymousUser()
        response = views.VerificationListView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_anonymous_start_is_rejected(self):
        request = RequestFactory().get("/api/verification/manage/1/start/")
        request.user = AnonymousUser()
        response = views.VerificationStartView.as_view()(request, pk=1)
        self.assertEqual(response.status_code, 302)
