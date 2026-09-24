from django import template

from library.services import build_public_trust_context_for_library


register = template.Library()


@register.inclusion_tag("partials/_trust_context.html")
def library_public_trust_context(library_item):
    return {"trust_context": build_public_trust_context_for_library(library_item)}
