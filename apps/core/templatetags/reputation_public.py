from django import template

from apps.core.services.public_reputation import get_public_reputation


register = template.Library()


@register.simple_tag
def public_contextual_reputation(user):
    if user is None or not getattr(user, "pk", None):
        return []
    return get_public_reputation(user)
