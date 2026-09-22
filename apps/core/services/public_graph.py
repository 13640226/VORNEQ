"""Disclosure-safe, read-only Public Graph V1 projection."""

from django.db import transaction

from apps.core.models import Artifact, ArtifactBinding
from apps.evidence.models import ProvenanceStep
from apps.verification.public import get_public_evidence_projection
from apps.verification.services.target_identity import CanonicalTargetConflict
from library.models import LibraryItem
from marketplace.models import Product


EVIDENCE_LIMIT = 25
PROVENANCE_LIMIT = 10
SUPPORTED_TARGETS = {
    ("marketplace", "product"),
    ("library", "libraryitem"),
}


class PublicGraphUnavailable(LookupError):
    """Raised when a root cannot be disclosed under the public graph contract."""


def _is_public_content(content_object):
    if isinstance(content_object, Product):
        return content_object.is_public
    if isinstance(content_object, LibraryItem):
        return content_object.is_published
    return False


def _resolve_root(artifact_id):
    artifact = (
        Artifact.objects.select_related("binding__content_type")
        .filter(pk=artifact_id, is_active=True)
        .first()
    )
    if artifact is None:
        raise PublicGraphUnavailable

    try:
        binding = artifact.binding
    except ArtifactBinding.DoesNotExist as exc:
        raise PublicGraphUnavailable from exc

    target = (binding.content_type.app_label, binding.content_type.model)
    if target not in SUPPORTED_TARGETS:
        raise PublicGraphUnavailable

    content_object = binding.content_object
    if content_object is None or not _is_public_content(content_object):
        raise PublicGraphUnavailable

    return artifact, content_object, target[1]


def _public_evidence_refs(content_object, artifact_type):
    try:
        projection = get_public_evidence_projection(content_object, artifact_type)
    except CanonicalTargetConflict as exc:
        raise PublicGraphUnavailable from exc

    refs = {
        evidence["evidence_id"]
        for claim in projection["claims"]
        for evidence in claim["evidences"]
    }
    return sorted(refs)


def _provenance_for_evidence(evidence_ref):
    # ProvenanceStep is immutable. Its canonical UUID is used only as an
    # internal deterministic tie-break and is never emitted.
    return list(
        ProvenanceStep.objects.filter(evidence_id=evidence_ref)
        .order_by("timestamp", "id")[: PROVENANCE_LIMIT + 1]
    )


@transaction.atomic
def get_public_graph(artifact_id):
    """Build the bounded Public Graph V1 DTO from canonical public authorities."""
    artifact, content_object, artifact_type = _resolve_root(artifact_id)

    evidence_refs = _public_evidence_refs(content_object, artifact_type)
    evidence_truncated = len(evidence_refs) > EVIDENCE_LIMIT
    emitted_evidence_refs = evidence_refs[:EVIDENCE_LIMIT]

    root_ref = str(artifact.pk)
    root = {
        "type": "artifact",
        "ref": root_ref,
        "truncated": evidence_truncated,
    }
    nodes = []
    edges = []

    provenance_ordinal = 0
    for evidence_ref in emitted_evidence_refs:
        steps = _provenance_for_evidence(evidence_ref)
        provenance_truncated = len(steps) > PROVENANCE_LIMIT
        emitted_steps = steps[:PROVENANCE_LIMIT]

        evidence_node = {
            "type": "evidence",
            "ref": evidence_ref,
            "truncated": provenance_truncated,
        }
        nodes.append(evidence_node)
        edges.append(
            {
                "source": {"type": "artifact", "ref": root_ref},
                "target": {"type": "evidence", "ref": evidence_ref},
                "relation": "INCLUDES_EVIDENCE",
            }
        )

        for step in emitted_steps:
            provenance_ordinal += 1
            local_ref = f"p{provenance_ordinal}"
            nodes.append(
                {
                    "type": "provenance",
                    "ref": local_ref,
                    "source_type": step.source_type,
                    "timestamp": step.timestamp,
                }
            )
            edges.append(
                {
                    "source": {"type": "evidence", "ref": evidence_ref},
                    "target": {"type": "provenance", "ref": local_ref},
                    "relation": "HAS_PROVENANCE",
                }
            )

    # Revalidate the disclosure authorities after construction. If publication,
    # binding, verification visibility, or eligibility changed during the
    # request, fail closed instead of returning a mixed-state projection.
    revalidated_artifact, revalidated_content, revalidated_type = _resolve_root(
        artifact_id
    )
    revalidated_refs = _public_evidence_refs(revalidated_content, revalidated_type)
    if (
        revalidated_artifact.pk != artifact.pk
        or revalidated_type != artifact_type
        or revalidated_refs != evidence_refs
    ):
        raise PublicGraphUnavailable

    return {"root": root, "nodes": nodes, "edges": edges}
