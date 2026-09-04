from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.evidence.models import Claim, ContentVersion


class ReadPathPurityTests(TestCase):
    """GET endpoints in graph/analysis must not issue INSERT/UPDATE/DELETE SQL."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="read-purity-user",
            password="test-pass-123",
        )
        self.claim = Claim.objects.create(
            claim_text="Read-path purity regression claim",
            scope="test",
            created_by=self.user,
        )
        self.client.force_login(self.user)

        ContentVersion.objects.create(
            claim=self.claim,
            version_number=1,
            snapshot={"claim_text": "v1", "scope": "test"},
            created_by=self.user,
        )
        ContentVersion.objects.create(
            claim=self.claim,
            version_number=2,
            snapshot={"claim_text": "v2", "scope": "test"},
            created_by=self.user,
        )

    def assert_get_is_sql_read_only(self, url):
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        write_queries = [
            query["sql"]
            for query in captured.captured_queries
            if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertEqual(
            write_queries,
            [],
            msg=f"SQL writes detected on GET {url}:\n" + "\n".join(write_queries),
        )

    def test_claim_graph_is_read_only(self):
        self.assert_get_is_sql_read_only(
            reverse("graph:claim-graph", kwargs={"claim_id": self.claim.pk})
        )

    def test_disagreement_map_is_read_only(self):
        self.assert_get_is_sql_read_only(
            reverse("graph:disagreement-map", kwargs={"claim_id": self.claim.pk})
        )

    def test_evidence_gaps_is_read_only(self):
        self.assert_get_is_sql_read_only(
            reverse("graph:evidence-gaps", kwargs={"claim_id": self.claim.pk})
        )

    def test_knowledge_history_is_read_only(self):
        self.assert_get_is_sql_read_only(
            reverse("graph:knowledge-history", kwargs={"claim_id": self.claim.pk})
        )

    def test_knowledge_diff_is_read_only(self):
        self.assert_get_is_sql_read_only(
            reverse(
                "graph:knowledge-diff",
                kwargs={
                    "claim_id": self.claim.pk,
                    "from_version": 1,
                    "to_version": 2,
                },
            )
        )

    def test_prediction_ledger_is_read_only(self):
        self.assert_get_is_sql_read_only(
            reverse("graph:prediction-ledger", kwargs={"claim_id": self.claim.pk})
        )

    def test_decision_package_is_read_only(self):
        self.assert_get_is_sql_read_only(
            reverse("graph:decision-package", kwargs={"claim_id": self.claim.pk})
        )

    def test_demo_dashboard_is_read_only(self):
        self.assert_get_is_sql_read_only(
            reverse("graph:demo-dashboard", kwargs={"claim_id": self.claim.pk})
        )
