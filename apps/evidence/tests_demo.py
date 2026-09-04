from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.evidence.management.commands.create_demo_scenario import DEMO_SCOPE
from apps.evidence.models import Claim, Critique, Evidence, EvidenceRelation, Prediction


class EndToEndDemoTests(TestCase):
    def test_demo_command_is_idempotent_and_dashboard_renders(self):
        call_command("create_demo_scenario", verbosity=0)
        claim = Claim.objects.get(scope=DEMO_SCOPE)

        self.assertEqual(claim.content_versions.count(), 2)
        self.assertEqual(Evidence.objects.filter(metadata__demo=True).count(), 4)
        self.assertEqual(
            EvidenceRelation.objects.filter(claim=claim, retired_at__isnull=True).count(),
            4,
        )
        self.assertEqual(Critique.objects.filter(claim=claim).count(), 3)
        self.assertEqual(Prediction.objects.filter(claim=claim).count(), 2)
        self.assertEqual(claim.change_conditions.count(), 1)

        self.client.force_login(claim.created_by)
        response = self.client.get(
            reverse("graph:demo-dashboard", kwargs={"claim_id": claim.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DeepTech diligence demo")
        self.assertContains(response, "Illustrative synthetic scenario")
        self.assertContains(response, "Prediction Ledger")
        self.assertContains(response, "Knowledge Diff")

        call_command("create_demo_scenario", verbosity=0)
        claim.refresh_from_db()
        self.assertEqual(Claim.objects.filter(scope=DEMO_SCOPE).count(), 1)
        self.assertEqual(claim.content_versions.count(), 2)
        self.assertEqual(Evidence.objects.filter(metadata__demo=True).count(), 4)
        self.assertEqual(Prediction.objects.filter(claim=claim).count(), 2)
