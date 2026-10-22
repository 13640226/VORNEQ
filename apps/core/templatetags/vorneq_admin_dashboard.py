"""Permission-aware dashboard data for the Django admin home page."""
from urllib.parse import urlencode

from django.apps import apps
from django import template
from django.contrib import admin
from django.urls import NoReverseMatch, reverse

register = template.Library()

CARDS = (
    ("content", "article", "مقالات", "article", {}),
    ("marketplace", "product", "محصولات", "product", {}),
    ("media", "mediaasset", "رسانه‌ها", "media", {}),
    (
        "verification", "verificationrequest",
        "درخواست‌های در انتظار بررسی", "verification",
        {"status__in": ("requested", "in_progress")},
    ),
)


@register.simple_tag(takes_context=True)
def vorneq_dashboard(context):
    """Only query and link to registered models the staff user can access."""
    request = context["request"]
    user = request.user
    result = {"cards": [], "actions": []}
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return result

    for app_label, model_name, title, tone, filters in CARDS:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        model_admin = admin.site._registry.get(model)
        if model_admin is None:
            continue

        base_name = f"admin:{app_label}_{model_name}"
        if model_admin.has_view_permission(request):
            try:
                url = reverse(f"{base_name}_changelist", current_app=admin.site.name)
            except NoReverseMatch:
                pass
            else:
                if filters:
                    url += "?" + urlencode(filters, doseq=True)
                result["cards"].append({
                    "title": title,
                    "value": model._default_manager.filter(**filters).count(),
                    "url": url,
                    "tone": tone,
                })

        if model_admin.has_add_permission(request):
            try:
                add_url = reverse(f"{base_name}_add", current_app=admin.site.name)
            except NoReverseMatch:
                continue
            result["actions"].append({"title": title, "url": add_url})
    return result
