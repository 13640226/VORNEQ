from django import template

from apps.verification.public import (
    get_public_evidence_projection,
    get_public_verification_summary,
)


register = template.Library()


@register.simple_tag
def public_verification_summary(artifact):
    return get_public_verification_summary(artifact)


@register.simple_tag
def public_evidence_projection(artifact, artifact_type="product"):
    return get_public_evidence_projection(artifact, artifact_type)
