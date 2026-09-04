from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.evidence.models import Claim
from apps.evidence.services import DecisionPackageService

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
def decision_package(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    package = DecisionPackageService.build(claim)
    package["truth_graph"] = TruthGraphService.build_claim_graph(claim)
    package["disagreement_map"] = DisagreementMapService.build(claim)
    package["evidence_gaps"] = EvidenceGapFinderService.build(claim)
    return JsonResponse(package)
