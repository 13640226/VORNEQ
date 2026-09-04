from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.services import ReputationService
from apps.evidence.models import ChangeCondition, Claim, Critique, Evidence, EvidenceRelation, Prediction
from apps.evidence.services import ContentVersionService, EvidenceService, PredictionLedgerService, RelationService


DEMO_SCOPE = "DEMO: Energy Storage / Battery Technology"
INITIAL_CLAIM = (
    "Solid-state batteries will achieve energy density > 500 Wh/kg by 2028."
)
CURRENT_CLAIM = (
    "Solid-state batteries with lithium-metal anodes may achieve energy density > 500 Wh/kg "
    "and cycle life > 1,000 cycles by 2028, provided scale-up challenges are resolved."
)


class Command(BaseCommand):
    help = "Create an illustrative end-to-end DeepTech diligence demo scenario."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        users = {}
        for username in ("demo_researcher", "demo_analyst", "demo_engineer"):
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            users[username] = user

        researcher = users["demo_researcher"]
        analyst = users["demo_analyst"]
        engineer = users["demo_engineer"]

        claim = Claim.objects.filter(scope=DEMO_SCOPE).order_by("created_at").first()
        if claim is None:
            claim = Claim.objects.create(
                claim_text=INITIAL_CLAIM,
                scope=DEMO_SCOPE,
                created_by=researcher,
            )

        claim = ContentVersionService.update_claim(
            claim=claim,
            claim_text=CURRENT_CLAIM,
            change_note=(
                "Added uncertainty and an explicit scale-up condition after critical review."
            ),
            created_by=researcher,
        )

        evidence_specs = [
            {
                "key": "lab-performance",
                "content": (
                    "Illustrative laboratory report: a lithium-metal solid-state prototype "
                    "demonstrates approximately 450 Wh/kg under controlled test conditions."
                ),
                "source_ref": "demo://battery/lab-performance",
                "relation": EvidenceRelation.RelationType.SUPPORTS,
                "basis": "Laboratory performance supports the direction of the energy-density claim.",
                "source_type": "document",
            },
            {
                "key": "industrial-roadmap",
                "content": (
                    "Illustrative industry roadmap: pilot-to-production scale-up is targeted for "
                    "the 2027-2028 window, subject to manufacturing yield and cost targets."
                ),
                "source_ref": "demo://battery/industrial-roadmap",
                "relation": EvidenceRelation.RelationType.SUPPORTS,
                "basis": "The roadmap supports feasibility of the time window but is not independent validation.",
                "source_type": "document",
            },
            {
                "key": "scale-up-review",
                "content": (
                    "Illustrative independent critical review: interface stability, manufacturing "
                    "yield, cost, and long-cycle durability remain unresolved at commercial scale."
                ),
                "source_ref": "demo://battery/scale-up-review",
                "relation": EvidenceRelation.RelationType.CONTRADICTS,
                "basis": "Unresolved scale-up constraints challenge the combined 2028 performance target.",
                "source_type": "document",
            },
            {
                "key": "meta-analysis",
                "content": (
                    "Illustrative meta-analysis: progress is material, but evidence is insufficient "
                    "to conclude that >500 Wh/kg and >1,000 cycles will both be reached by 2028."
                ),
                "source_ref": "demo://battery/meta-analysis",
                "relation": EvidenceRelation.RelationType.CONTEXTUALIZES,
                "basis": "Synthesizes uncertainty without asserting a binary verdict.",
                "source_type": "document",
            },
        ]

        evidence_by_key = {}
        for spec in evidence_specs:
            evidence = Evidence.objects.filter(
                metadata__demo_key=spec["key"], created_by=researcher
            ).first()
            if evidence is None:
                evidence = EvidenceService.create_with_provenance(
                    content=spec["content"],
                    source_ref=spec["source_ref"],
                    source_type=spec["source_type"],
                    metadata={"demo": True, "demo_key": spec["key"], "synthetic": True},
                    created_by=researcher,
                    note="Illustrative synthetic demo evidence; not a claim about a real publication.",
                )
            evidence_by_key[spec["key"]] = evidence

            relation = RelationService.get_active_relation(claim=claim, evidence=evidence)
            if relation is None:
                relation = RelationService.create(
                    claim=claim,
                    evidence=evidence,
                    relation=spec["relation"],
                    relation_basis=spec["basis"],
                    created_by=researcher,
                )

        critiques = [
            (
                Critique.Category.DATA,
                "Do controlled laboratory results generalize to high-yield commercial production?",
            ),
            (
                Critique.Category.METHOD,
                "Roadmap milestones and independent durability tests use different success criteria.",
            ),
            (
                Critique.Category.INTERPRETATION,
                "Material progress does not by itself establish that the combined 2028 threshold will be reached.",
            ),
        ]
        for category, body in critiques:
            Critique.objects.get_or_create(
                claim=claim,
                relation=None,
                category=category,
                body=body,
                defaults={"created_by": researcher},
            )

        ChangeCondition.objects.get_or_create(
            claim=claim,
            description=(
                "Independent commercial-scale validation demonstrates >500 Wh/kg and >1,000 cycles "
                "with a disclosed test protocol."
            ),
            defaults={
                "evidence_required": "Independent validation with disclosed protocol and scale context.",
                "severity": ChangeCondition.Severity.HIGH,
            },
        )

        due = timezone.make_aware(datetime(2028, 12, 31, 12, 0, 0))
        prediction_specs = [
            (analyst, "0.6500", "Optimistic weighting of laboratory progress and industrial roadmap."),
            (engineer, "0.4000", "Scale-up and durability uncertainty remain material."),
        ]
        for user, probability, rationale in prediction_specs:
            if not Prediction.objects.filter(claim=claim, created_by=user).exists():
                PredictionLedgerService.create(
                    claim=claim,
                    event_statement=(
                        "By 2028-12-31, a commercially relevant lithium-metal solid-state battery "
                        "demonstrates >500 Wh/kg and >1,000 cycles under a disclosed protocol."
                    ),
                    probability=probability,
                    resolution_date=due,
                    rationale=rationale,
                    created_by=user,
                )

        ReputationService.recalculate_all(researcher)
        ReputationService.recalculate_all(analyst)
        ReputationService.recalculate_all(engineer)

        self.stdout.write(self.style.SUCCESS(f"Demo scenario ready. Claim: {claim.pk}"))
        self.stdout.write(
            "Evidence sources are explicitly synthetic demo records. Prediction scoring remains pending until resolution."
        )
