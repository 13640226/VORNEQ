from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.evidence.models import Claim, ContentVersion
from apps.evidence.services import (
    ContentVersionService,
    DecisionPackageService,
    PredictionLedgerService,
)

from .analysis import DisagreementMapService, EvidenceGapFinderService
from .services import TruthGraphService


@require_GET
def claim_graph(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(TruthGraphService.build_claim_graph(claim))


@require_GET
def disagreement_map(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(DisagreementMapService.build(claim))


@require_GET
def evidence_gaps(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(EvidenceGapFinderService.build(claim))


@require_GET
def knowledge_history(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    return JsonResponse(
        {
            "claim_id": str(claim.id),
            "versions": ContentVersionService.history(claim),
        }
    )


@require_GET
def knowledge_diff(request, claim_id, from_version, to_version):
    claim = get_object_or_404(Claim, pk=claim_id)
    before = get_object_or_404(ContentVersion, claim=claim, version_number=from_version)
    after = get_object_or_404(ContentVersion, claim=claim, version_number=to_version)
    return JsonResponse(ContentVersionService.compare(before=before, after=after))


@require_GET
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
