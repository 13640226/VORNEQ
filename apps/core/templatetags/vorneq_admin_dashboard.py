"""Permission-aware dashboard data for the Django admin home page.

Read-only: it counts rows and builds admin URLs, and never changes data.
Every card, status, and quick action is filtered by the ModelAdmin's own
view/add permission checks, so staff only see what they may already open.
"""
import os
from urllib.parse import urlencode

from django import template
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.db.models import Count
from django.urls import NoReverseMatch, reverse

register = template.Library()

# (app_label, model_name, card title, singular label for "add", tone)
CARDS = (
    ("content", "article", "مقالات", "مقاله", "article"),
    ("marketplace", "product", "محصولات", "محصول", "product"),
    ("media", "mediaasset", "رسانه‌ها", "رسانه", "media"),
    ("library", "libraryitem", "اسناد کتابخانه", "سند کتابخانه", "library"),
)

# Quick actions in display order: (app_label, model_name, label)
ACTIONS = (
    ("content", "article", "افزودن مقاله"),
    ("marketplace", "product", "افزودن محصول"),
    ("media", "mediaasset", "بارگذاری رسانه"),
    ("verification", "verificationrequest", "ثبت درخواست راستی‌آزمایی"),
)

# Verification request lifecycle: (status value, label, tone)
VERIFICATION_STATUSES = (
    ("requested", "ثبت‌شده", "idle"),
    ("in_progress", "در حال بررسی", "warn"),
    ("completed", "تکمیل‌شده", "ok"),
    ("failed", "ناموفق", "bad"),
    ("cancelled", "لغوشده", "muted"),
)

ENV_LABELS = {
    "production": "Production",
    "staging": "Staging",
    "development": "Development",
    "test": "Test",
}


def _model_admin(app_label, model_name):
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return None, None
    return model, admin.site._registry.get(model)


def _url(app_label, model_name, view):
    try:
        return reverse(f"admin:{app_label}_{model_name}_{view}", current_app=admin.site.name)
    except NoReverseMatch:
        return None


def _staff(request):
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


def _verification(request):
    model, model_admin = _model_admin("verification", "verificationrequest")
    if model is None or model_admin is None or not model_admin.has_view_permission(request):
        return None
    changelist = _url("verification", "verificationrequest", "changelist")
    if changelist is None:
        return None

    counts = {
        row["status"]: row["n"]
        for row in model._default_manager.order_by().values("status").annotate(n=Count("pk"))
    }
    total = sum(counts.values())
    statuses = []
    for value, label, tone in VERIFICATION_STATUSES:
        number = counts.get(value, 0)
        statuses.append({
            "value": value,
            "label": label,
            "tone": tone,
            "count": number,
            "percent": round(number * 100 / total, 2) if total else 0,
            "url": f"{changelist}?{urlencode({'status__exact': value})}",
        })
    pending = counts.get("requested", 0) + counts.get("in_progress", 0)
    return {
        "total": total,
        "pending": pending,
        "statuses": statuses,
        "url": changelist,
        "pending_url": f"{changelist}?{urlencode({'status__in': 'requested,in_progress'})}",
    }


@register.simple_tag(takes_context=True)
def vorneq_dashboard(context):
    """Collect the cards, quick actions and verification summary for this user."""
    request = context["request"]
    result = {"cards": [], "actions": [], "verification": None}
    if not _staff(request):
        return result

    for app_label, model_name, title, singular, tone in CARDS:
        model, model_admin = _model_admin(app_label, model_name)
        if model_admin is None or not model_admin.has_view_permission(request):
            continue
        url = _url(app_label, model_name, "changelist")
        if url is None:
            continue
        result["cards"].append({
            "title": title,
            "singular": singular,
            "value": model._default_manager.count(),
            "url": url,
            "tone": tone,
        })

    for app_label, model_name, label in ACTIONS:
        _model, model_admin = _model_admin(app_label, model_name)
        if model_admin is None or not model_admin.has_add_permission(request):
            continue
        url = _url(app_label, model_name, "add")
        if url is not None:
            result["actions"].append({"title": label, "url": url})

    result["verification"] = _verification(request)
    return result


@register.simple_tag(takes_context=True)
def vorneq_environment(context):
    """Environment badge for staff: which deployment and database this is."""
    if not _staff(context.get("request")):
        return None
    env = getattr(settings, "VORNEQ_ENV", "") or ""
    return {
        "key": env,
        "label": ENV_LABELS.get(env, env or "Unknown"),
        "database": os.path.basename(str(connection.settings_dict.get("NAME") or "")),
    }
