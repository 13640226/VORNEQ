from apps.evidence.models import EvidenceRelation, EvidenceState


class DecisionPackageService:
    """Build a read-only, portable decision package from canonical evidence data."""

    @classmethod
    def build(cls, claim):
        relations = list(
            EvidenceRelation.objects.filter(claim=claim, retired_at__isnull=True)
            .select_related("evidence")
            .prefetch_related("evidence__provenance_chain")
            .order_by("created_at", "id")
        )

        state = EvidenceState.objects.filter(claim=claim).first()
        state_values = (
            {
                "state": state.state,
                "supporting_count": state.supporting_count,
                "contradicting_count": state.contradicting_count,
                "neutral_count": state.neutral_count,
                "evidence_count": state.evidence_count,
            }
            if state
            else EvidenceState.derive_values(claim)
        )

        evidence_items = []
        for relation in relations:
            evidence = relation.evidence
            evidence_items.append(
                {
                    "evidence_id": str(evidence.id),
                    "relation_id": str(relation.id),
                    "relation": relation.relation,
                    "relation_basis": relation.relation_basis,
                    "content_type": evidence.content_type,
                    "content": evidence.content,
                    "observed_at": evidence.observed_at.isoformat() if evidence.observed_at else None,
                    "integrity_digest": evidence.integrity_digest,
                    "provenance": [
                        {
                            "source_type": step.source_type,
                            "source_ref": step.source_ref,
                            "transformation": step.transformation,
                            "timestamp": step.timestamp.isoformat(),
                            "note": step.note,
                        }
                        for step in evidence.provenance_chain.all()
                    ],
                }
            )

        versions = list(claim.content_versions.order_by("version_number"))
        current_version = versions[-1] if versions else None

        return {
            "claim": {
                "id": str(claim.id),
                "claim_text": claim.claim_text,
                "scope": claim.scope,
            },
            "knowledge_version": {
                "current_version": current_version.version_number if current_version else None,
                "version_count": len(versions),
                "last_change_note": current_version.change_note if current_version else "",
                "last_version_at": current_version.created_at.isoformat() if current_version else None,
            },
            "evidence_state": state_values,
            "evidence": evidence_items,
            "change_conditions": [
                {
                    "id": str(condition.id),
                    "description": condition.description,
                    "evidence_required": condition.evidence_required,
                    "severity": condition.severity,
                }
                for condition in claim.change_conditions.all().order_by("created_at", "id")
            ],
        }

    @classmethod
    def to_markdown(cls, claim):
        package = cls.build(claim)
        lines = [
            f"# Decision Record: {package['claim']['claim_text']}",
            "",
            f"**Scope:** {package['claim']['scope'] or '—'}",
            f"**Knowledge version:** {package['knowledge_version']['current_version'] or 'unversioned'}",
            f"**Evidence state:** {package['evidence_state']['state']}",
            f"**Distinct evidence:** {package['evidence_state']['evidence_count']}",
            "",
            "## Evidence",
            "",
        ]

        for item in package["evidence"]:
            lines.extend(
                [
                    f"### {item['relation'].title()} — {item['evidence_id']}",
                    item["content"],
                    "",
                    f"Integrity digest: `{item['integrity_digest']}`",
                    f"Relation basis: {item['relation_basis'] or '—'}",
                    "",
                ]
            )
            if item["provenance"]:
                lines.append("Provenance:")
                for step in item["provenance"]:
                    lines.append(
                        f"- {step['source_type']}: {step['source_ref']}"
                        + (f" — {step['transformation']}" if step["transformation"] else "")
                    )
                lines.append("")

        if package["change_conditions"]:
            lines.extend(["## Change Conditions", ""])
            for condition in package["change_conditions"]:
                lines.append(f"- {condition['description']} ({condition['severity']})")

        return "\n".join(lines).rstrip() + "\n"
