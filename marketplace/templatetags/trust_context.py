from django import template

from marketplace.services import build_public_trust_context


register = template.Library()


@register.inclusion_tag("partials/_trust_context.html")
def public_trust_context(product):
    return {"trust_context": build_public_trust_context(product)}
