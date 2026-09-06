from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import QualitySignal
from apps.verification.models import VerificationRequest


V1_ELIGIBLE_SIGNAL_TYPES = {
    QualitySignal.SignalType.EXTERNAL_REFERENCE,
    QualitySignal.SignalType.REPRODUCIBILITY,
    QualitySignal.SignalType.ADJUDICATION,
    QualitySignal.SignalType.INDEPENDENT_CORROBORATION,
}


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    reasons: tuple[str, ...]


def evaluate_signal_eligibility(signal: QualitySignal) -> EligibilityDecision:
    """Evaluate ADR-003 eligibility without scoring reputation."""
    reasons = []
    result = signal.verification_result

    if result.request.status != VerificationRequest.Status.COMPLETED:
        reasons.append("verification_result_not_completed")

    if signal.signal_type not in V1_ELIGIBLE_SIGNAL_TYPES:
        reasons.append("signal_type_not_eligible_in_v1")

    if not signal.source_ref.strip():
        reasons.append("missing_source_ref")

    if not signal.domain.strip():
        reasons.append("missing_domain")

    if signal.method_id != result.request.method_id:
        reasons.append("verification_method_mismatch")

    if not signal.provenance_ref.strip() and signal.evidence_relation_id is None:
        reasons.append("missing_provenance")

    if not signal.independence_declared:
        reasons.append("independence_not_declared")
    elif not signal.independence_basis.strip():
        reasons.append("missing_independence_basis")

    if signal.assessor_id is not None and signal.assessor_id == result.verifier_id:
        reasons.append("self_assessment_not_allowed")

    if signal.evidence_relation_id is not None:
        if signal.evidence_relation.claim_id != result.request.claim_id:
            reasons.append("evidence_relation_claim_mismatch")

    if signal.policy_version != "eligibility-v1":
        reasons.append("unsupported_policy_version")

    return EligibilityDecision(eligible=not reasons, reasons=tuple(reasons))


@transaction.atomic
def create_quality_signal(
    *,
    verification_result,
    signal_type,
    source_ref,
    domain,
    method,
    assessor=None,
    provenance_ref="",
    evidence_relation=None,
    independence_declared=False,
    independence_basis="",
    observed_at=None,
    metadata=None,
    policy_version="eligibility-v1",
):
    """Create one immutable signal and persist its versioned eligibility decision."""
    signal = QualitySignal(
        verification_result=verification_result,
        signal_type=signal_type,
        assessor=assessor,
        source_ref=source_ref,
        provenance_ref=provenance_ref,
        evidence_relation=evidence_relation,
        independence_declared=independence_declared,
        independence_basis=independence_basis,
        domain=domain,
        method=method,
        observed_at=observed_at or timezone.now(),
        policy_version=policy_version,
        metadata=metadata or {},
    )
    decision = evaluate_signal_eligibility(signal)
    signal.is_eligible = decision.eligible
    signal.eligibility_reasons = list(decision.reasons)
    signal.full_clean()
    signal.save()
    return signal
