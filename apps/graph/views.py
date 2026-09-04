from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.core.services import ReputationService
from apps.evidence.models import Claim, ContentVersion
from apps.evidence.services import (
    ContentVersionService,
    DecisionPackageService,
    PredictionLedgerService,
)

from .analysis import DisagreementMapService, EvidenceGapFinderService
from .services import TruthGraphService


@require_GET
@login_required
def claim_graph(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(TruthGraphService.build_claim_graph(claim))


@require_GET
@login_required
def disagreement_map(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(DisagreementMapService.build(claim))


@require_GET
@login_required
def evidence_gaps(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(EvidenceGapFinderService.build(claim))


@require_GET
@login_required
def knowledge_history(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(
        {
            "claim_id": str(claim.id),
            "versions": ContentVersionService.history(claim),
        }
    )


@require_GET
@login_required
def knowledge_diff(request, claim_id, from_version, to_version):
    claim = get_object_or_404(Claim, pk=claim_id)
    before = get_object_or_404(ContentVersion, claim=claim, version_number=from_version)
    after = get_object_or_404(ContentVersion, claim=claim, version_number=to_version)
    return JsonResponse(ContentVersionService.compare(before=before, after=after))


@require_GET
@login_required
def prediction_ledger(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(
        {
            "claim_id": str(claim.id),
            "predictions": PredictionLedgerService.ledger(claim),
            "scoring_summary": PredictionLedgerService.scoring_summary(claim=claim),
        }
    )


@require_GET
@login_required
def demo_dashboard(request, claim_id):
    """Read-only presentation layer over the already-implemented pilot services."""
    claim = get_object_or_404(Claim, pk=claim_id)
    history = list(ContentVersion.objects.filter(claim=claim).order_by("version_number"))
    latest_diff = None
    if len(history) >= 2:
        latest_diff = ContentVersionService.compare(before=history[-2], after=history[-1])

    prediction_rows = PredictionLedgerService.ledger(claim)
    related_user_ids = {claim.created_by_id} if claim.created_by_id else set()
    related_user_ids.update(
        row["created_by"] for row in prediction_rows if row.get("created_by") is not None
    )
    User = claim._meta.get_field("created_by").remote_field.model
    reputations = []
    for user in User.objects.filter(pk__in=related_user_ids).order_by("username"):
        snapshot = ReputationService.snapshot(user)
        snapshot["username"] = user.get_username()
        reputations.append(snapshot)

    context = {
        "claim": claim,
        "package": DecisionPackageService.build(claim),
        "graph": TruthGraphService.build_claim_graph(claim),
        "disagreements": DisagreementMapService.build(claim),
        "gaps": EvidenceGapFinderService.build(claim),
        "knowledge_history": ContentVersionService.history(claim),
        "latest_diff": latest_diff,
        "predictions": prediction_rows,
        "prediction_summary": PredictionLedgerService.scoring_summary(claim=claim),
        "reputations": reputations,
    }
    return render(request, "graph/demo_dashboard.html", context)


@require_GET
@login_required
def decision_package(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    package = DecisionPackageService.build(claim)
    package["truth_graph"] = TruthGraphService.build_claim_graph(claim)
    package["disagreement_map"] = DisagreementMapService.build(claim)
    package["evidence_gaps"] = EvidenceGapFinderService.build(claim)
    package["knowledge_history"] = ContentVersionService.history(claim)
    package["prediction_ledger"] = {
        "predictions": PredictionLedgerService.ledger(claim),
        "scoring_summary": PredictionLedgerService.scoring_summary(claim=claim),
    }
    return JsonResponse(package)
