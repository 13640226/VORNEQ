from django import template

from apps.core.services.entitlement import has_valid_entitlement


register = template.Library()


@register.simple_tag
def has_product_entitlement(user, product):
    return has_valid_entitlement(user, product)
