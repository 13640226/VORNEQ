from apps.evidence.models import (
    ConditionObservation,
    Critique,
    EvidenceRelation,
    EvidenceState,
)


class DisagreementMapService:
    """Build a transparent, read-only map of structured disagreements for a claim."""

    @classmethod
    def build(cls, claim):
        categories = {
            value: []
            for value in Critique.Category.values
        }

        critiques = (
            Critique.objects.filter(claim=claim)
            | Critique.objects.filter(relation__claim=claim)
        ).distinct().select_related("relation")

        for critique in critiques.order_by("created_at", "id"):
            target_type = "relation" if critique.relation_id else "claim"
            target_id = critique.relation_id or critique.claim_id
            categories[critique.category].append(
                {
                    "critique_id": str(critique.id),
                    "target_type": target_type,
                    "target_id": str(target_id),
                    "body": critique.body,
                    "created_at": critique.created_at.isoformat(),
                }
            )

        contradicting_relations = list(
            EvidenceRelation.objects.filter(
                claim=claim,
                retired_at__isnull=True,
                relation=EvidenceRelation.RelationType.CONTRADICTS,
            )
            .select_related("evidence")
            .order_by("created_at", "id")
        )

        return {
            "claim_id": str(claim.id),
            "categories": categories,
            "category_counts": {
                key: len(items)
                for key, items in categories.items()
            },
            "contradicting_evidence": [
                {
                    "relation_id": str(relation.id),
                    "evidence_id": str(relation.evidence_id),
                    "content": relation.evidence.content,
                    "relation_basis": relation.relation_basis,
                }
                for relation in contradicting_relations
            ],
            "note": (
                "Critique categories are human-structured. Contradicting evidence is "
                "reported separately and is not automatically assigned a disagreement category."
            ),
        }


class EvidenceGapFinderService:
    """Identify explicit evidence gaps without making a truth or confidence verdict."""

    @staticmethod
    def _gap(code, severity, message, **context):
        return {
            "code": code,
            "severity": severity,
            "message": message,
            "context": context,
        }

    @classmethod
    def build(cls, claim):
        gaps = []
        active = list(
            EvidenceRelation.objects.filter(
                claim=claim,
                retired_at__isnull=True,
            )
            .select_related("evidence")
            .prefetch_related("evidence__provenance_chain")
            .order_by("created_at", "id")
        )

        state = EvidenceState.derive_values(claim)

        if not active:
            gaps.append(
                cls._gap(
                    "no_evidence",
                    "high",
                    "No active evidence is attached to this claim.",
                )
            )
        else:
            if state["supporting_count"] == 0:
                gaps.append(
                    cls._gap(
                        "no_supporting_evidence",
                        "medium",
                        "No active supporting evidence is attached to this claim.",
                    )
                )
            if state["contradicting_count"] == 0:
                gaps.append(
                    cls._gap(
                        "no_contradicting_evidence",
                        "medium",
                        "No active contradicting evidence is attached to this claim.",
                    )
                )
            if state["evidence_count"] == 1:
                gaps.append(
                    cls._gap(
                        "single_evidence_dependency",
                        "medium",
                        "The claim currently depends on a single distinct evidence item.",
                    )
                )

        for relation in active:
            evidence = relation.evidence
            if not list(evidence.provenance_chain.all()):
                gaps.append(
                    cls._gap(
                        "missing_provenance",
                        "high",
                        "An active evidence item has no provenance steps.",
                        evidence_id=str(evidence.id),
                        relation_id=str(relation.id),
                    )
                )

        for condition in claim.change_conditions.prefetch_related("observations").all():
            observations = list(condition.observations.all())
            latest = observations[0] if observations else None

            if latest is None:
                gaps.append(
                    cls._gap(
                        "unobserved_change_condition",
                        "high" if condition.severity == "high" else "medium",
                        "A change condition has never been observed.",
                        condition_id=str(condition.id),
                        evidence_required=condition.evidence_required,
                    )
                )
                continue

            if latest.observed_state in {
                ConditionObservation.ObservedState.UNKNOWN,
                ConditionObservation.ObservedState.POSSIBLY_MET,
                ConditionObservation.ObservedState.DISPUTED,
            }:
                gaps.append(
                    cls._gap(
                        "unresolved_change_condition",
                        "high" if condition.severity == "high" else "medium",
                        "The latest observation for a change condition remains unresolved.",
                        condition_id=str(condition.id),
                        observed_state=latest.observed_state,
                        evidence_required=condition.evidence_required,
                    )
                )

            if condition.evidence_required and latest.evidence_ref_id is None:
                gaps.append(
                    cls._gap(
                        "condition_evidence_missing",
                        "medium",
                        "A change condition specifies required evidence but its latest observation has no evidence reference.",
                        condition_id=str(condition.id),
                        evidence_required=condition.evidence_required,
                    )
                )

        severity_order = {"high": 0, "medium": 1, "low": 2}
        gaps.sort(key=lambda item: (severity_order[item["severity"]], item["code"]))

        return {
            "claim_id": str(claim.id),
            "evidence_state": state,
            "gap_count": len(gaps),
            "gaps": gaps,
            "note": (
                "Gaps are deterministic completeness checks. They do not determine whether "
                "the claim is true or false."
            ),
        }
