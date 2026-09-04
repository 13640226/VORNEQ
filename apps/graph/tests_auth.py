from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.evidence.models import Claim
from apps.evidence.services import ContentVersionService


class GraphAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="graph-auth-tester",
            password="test-pass-123",
        )
        self.claim = Claim.objects.create(
            claim_text="Test claim v1",
            scope="test",
            created_by=self.user,
        )
        ContentVersionService.update_claim(
            claim=self.claim,
            claim_text="Test claim v2",
            change_note="Create a second version for auth coverage.",
            created_by=self.user,
        )

    def _urls(self):
        return [
            reverse("graph:claim-graph", kwargs={"claim_id": self.claim.pk}),
            reverse("graph:disagreement-map", kwargs={"claim_id": self.claim.pk}),
            reverse("graph:evidence-gaps", kwargs={"claim_id": self.claim.pk}),
            reverse("graph:knowledge-history", kwargs={"claim_id": self.claim.pk}),
            reverse(
                "graph:knowledge-diff",
                kwargs={
                    "claim_id": self.claim.pk,
                    "from_version": 1,
                    "to_version": 2,
                },
            ),
            reverse("graph:prediction-ledger", kwargs={"claim_id": self.claim.pk}),
            reverse("graph:demo-dashboard", kwargs={"claim_id": self.claim.pk}),
            reverse("graph:decision-package", kwargs={"claim_id": self.claim.pk}),
        ]

    def test_graph_endpoints_require_login(self):
        for url in self._urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response.url)

    def test_graph_endpoints_allow_authenticated_get(self):
        self.client.force_login(self.user)
        for url in self._urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_graph_endpoints_reject_authenticated_non_get(self):
        self.client.force_login(self.user)
        for url in self._urls():
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertEqual(response.status_code, 405)
