"""PARITY-11 — read-only Environment-Parity-Snapshot und -Vergleich.

Erzeugt einen bereinigten, vergleichbaren JSON-Snapshot einer Laufzeitumgebung
(Staging, Production, lokal) und vergleicht zwei solche Snapshots.

Garantien:
* Nur lesend: keine Schreibzugriffe auf Datenbank, Storage, Cache, Queues.
* Keine externen Aufrufe. Gates, die eine Netzwerkprüfung bräuchten
  (Follow-Owner-Deployments), werden als NOT_VERIFIED gemeldet.
* Keine Secrets: Für Secrets, Tokens, Referenzen, Pins und Allowlists wird nur
  PRESENT/MISSING bzw. eine Anzahl/Übereinstimmung ausgegeben, nie der Wert.
* Keine personenbezogenen Daten: Konten erscheinen nur als Primärschlüssel
  mit Rollen- und Bindungsstatus (keine Namen, keine E-Mail-Adressen).
* Fail-closed: Jeder Abschnitt, der nicht vollständig gelesen werden kann,
  setzt ``status`` auf ``INVALID``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass

SNAPSHOT_VERSION = 1
STAGING_SERVICE_ID = "srv-dbm7dvc9v7es7393g70g"
PRODUCTION_SERVICE_ID = "srv-dadn07eq1p3s73eccau0"
_SHA = re.compile(r"[0-9a-f]{40}\Z")


# --------------------------------------------------------------------------
# Variablenkatalog
# --------------------------------------------------------------------------
# kind:
#   secret     – nur PRESENT/MISSING
#   reference  – Owner-Autorisierungsreferenz; nur PRESENT/MISSING
#   pin        – autorisierter SHA; nur MATCHES_RELEASE/MISMATCH/MISSING
#   allowlist  – Benutzer-ID-Liste; nur Anzahl gültiger Einträge
#   flag       – boolesch; Wert wird ausgegeben
#   config     – nicht geheime Konfiguration; Wert wird ausgegeben
#   host       – Domains/Origins/Service-IDs; Wert wird ausgegeben (Gruppe B)
#   runtime    – von Render gesetzt
#   tooling    – nur für lokale Werkzeuge/Tests; wird nicht verglichen
# scope: shared | staging | production | local
# parity:
#   must_match           – Unterschied ist Gruppe A (unnötig)
#   allowed_difference   – Gruppe B (bewusst getrennt)
#   staging_first        – Gruppe C (darf in Staging zuerst an sein)
#   informational        – wird berichtet, nicht bewertet

@dataclass(frozen=True)
class Var:
    name: str
    kind: str
    scope: str = "shared"
    parity: str = "must_match"


def _v(name, kind, scope="shared", parity=None):
    if parity is None:
        parity = {
            "secret": "allowed_difference", "reference": "allowed_difference",
            "pin": "allowed_difference", "allowlist": "allowed_difference",
            "host": "allowed_difference", "runtime": "informational",
            "tooling": "informational",
        }.get(kind, "must_match" if scope == "shared" else "allowed_difference")
    return Var(name, kind, scope, parity)


CATALOG: tuple[Var, ...] = (
    # Kern und Sicherheit
    _v("VORNEQ_ENV", "host"),
    _v("DJANGO_DEBUG", "flag"),
    _v("DJANGO_SECRET_KEY", "secret"),
    _v("DJANGO_ALLOWED_HOSTS", "host"),
    _v("DJANGO_CSRF_TRUSTED_ORIGINS", "host"),
    _v("DJANGO_LOG_LEVEL", "config", parity="informational"),
    _v("VORNEQ_PUBLIC_DOMAIN", "host"),
    _v("VORNEQ_DEFAULT_LANGUAGE", "config"),
    _v("ALLAUTH_TRUSTED_PROXY_COUNT", "config"),
    _v("ALLAUTH_TRUSTED_CLIENT_IP_HEADER", "config"),
    _v("ACCOUNT_EMAIL_VERIFICATION", "config"),
    _v("VORNEQ_METRICS_TOKEN", "secret"),
    # Datenbanken, Cache, Storage
    _v("DATABASE_URL", "secret"),
    _v("REDIS_URL", "secret"),
    _v("USE_OBJECT_STORAGE", "flag"),
    _v("OBJECT_STORAGE_BUCKET", "host"),
    _v("OBJECT_STORAGE_ENDPOINT_URL", "host"),
    _v("OBJECT_STORAGE_REGION", "host"),
    _v("OBJECT_STORAGE_ACCESS_KEY_ID", "secret"),
    _v("OBJECT_STORAGE_SECRET_ACCESS_KEY", "secret"),
    # E-Mail
    _v("EMAIL_BACKEND", "config", parity="allowed_difference"),
    _v("EMAIL_HOST", "host"),
    _v("EMAIL_PORT", "config", parity="allowed_difference"),
    _v("EMAIL_HOST_USER", "secret"),
    _v("EMAIL_HOST_PASSWORD", "secret"),
    _v("EMAIL_USE_TLS", "flag", parity="allowed_difference"),
    _v("DEFAULT_FROM_EMAIL", "host"),
    _v("RESEND_API_KEY", "secret"),
    # Render-Laufzeit
    _v("RENDER", "runtime"),
    _v("RENDER_SERVICE_ID", "host"),
    _v("RENDER_GIT_COMMIT", "runtime"),
    # Diagnose
    _v("VORNEQ_ACTOR_DIAGNOSTICS_ENABLED", "flag", "staging"),
    _v("VORNEQ_ACTOR_DIAGNOSTICS_IDENTITY_ID", "reference", "staging"),
    # KI – gemeinsam
    _v("OPENAI_API_KEY", "secret"),
    _v("VORNEQ_AI_DEPLOY_READ_TOKEN", "secret"),
    _v("VORNEQ_AI_EMERGENCY_STOP", "flag", parity="allowed_difference"),
    _v("VORNEQ_AI_CORE_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_PHASE_B_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_PHASE_B_MODEL", "config", parity="staging_first"),
    _v("VORNEQ_AI_PHASE_C_ENABLED", "flag", "local"),
    _v("VORNEQ_GLOBAL_AI_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_CONVERSATIONS_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_FEEDBACK_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CONVERSATIONS_ALLOWED_USER_IDS", "allowlist"),
    _v("VORNEQ_AI_CONTEXT_RETRIEVAL_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_RESPONSE_V3_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_RESPONSE_V3_STAGE2_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CHAT_BUDGET_MODEL", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CHAT_STREAMING_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_CHAT_JOBS_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_GLOBAL", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_PER_USER", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CHAT_JOB_LEASE_SECONDS", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CHAT_JOB_DEADLINE_SECONDS", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS", "flag", parity="allowed_difference"),
    _v("VORNEQ_AI_LEDGER_ENABLED", "flag", parity="allowed_difference"),
    _v("VORNEQ_AI_LEDGER_DATABASE_URL", "secret"),
    _v("VORNEQ_AI_LEDGER_ID", "reference"),
    _v("VORNEQ_AI_LEDGER_DB_NAME", "host"),
    # KI – Staging
    _v("VORNEQ_AI_STAGING_TRIAL_ENABLED", "flag", "staging"),
    _v("VORNEQ_AI_STAGING_OWNER_AUTH", "reference", "staging"),
    _v("VORNEQ_AI_STAGING_AUTHORIZED_SHA", "pin", "staging"),
    _v("VORNEQ_AI_STAGING_APPROVED_MODEL", "config", "staging"),
    _v("VORNEQ_AI_STAGING_ALLOWED_USER_IDS", "allowlist", "staging"),
    _v("VORNEQ_AI_STAGING_UNMETERED", "flag", "staging"),
    _v("VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD", "config", "staging"),
    _v("VORNEQ_AI_STAGING_RESERVE_MICROUSD", "config", "staging"),
    _v("VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS", "config", "staging"),
    _v("VORNEQ_AI_CHAT_RECOVERY_ENABLED", "flag", "staging"),
    _v("VORNEQ_AI_CHAT_STAGING_PREPAID_ONLY", "flag", "staging"),
    _v("VORNEQ_GLOBAL_AI_UNLIMITED_STAGING", "flag", "staging"),
    # KI – Production
    _v("VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED", "flag", "production"),
    _v("VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED", "flag", "production"),
    _v("VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT", "flag", "production"),
    _v("VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED", "flag", "production"),
    _v("VORNEQ_AI_CHAT_JOBS_PRODUCTION_ENABLED", "flag", "production"),
    _v("VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA", "pin", "production"),
    _v("VORNEQ_AI_PRODUCTION_OWNER_AUTH", "reference", "production"),
    _v("VORNEQ_AI_PRODUCTION_APPROVED_MODEL", "config", "production"),
    _v("VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS", "allowlist", "production"),
    _v("VORNEQ_AI_PRODUCTION_ACTOR_POLICY", "config", "production"),
    # Bild
    _v("VORNEQ_AI_IMAGE_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_IMAGE_PROVIDER", "config", parity="staging_first"),
    _v("VORNEQ_AI_IMAGE_MODEL", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_COMPLEXITY", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_MIN_INTERVAL_SECONDS", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_ALLOW_ZERO_INTERVAL", "flag", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_LEDGER_DAILY_MAX_REQUESTS", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_MAX_ACTIVE_JOBS_PER_USER", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_MAX_ACTIVE_JOBS_GLOBAL", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", "flag", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS", "flag", parity="allowed_difference"),
    _v("VORNEQ_AI_IMAGE_SAFETY_ID_KEY", "secret"),
    _v("VORNEQ_AI_IMAGE_LEDGER_ID", "reference"),
    _v("VORNEQ_OPENAI_IMAGE_API_KEY", "secret"),
    _v("VORNEQ_IMAGE_S3_BUCKET", "host"),
    _v("VORNEQ_IMAGE_S3_ENDPOINT_URL", "host"),
    _v("VORNEQ_IMAGE_S3_ACCESS_KEY_ID", "secret"),
    _v("VORNEQ_IMAGE_S3_SECRET_ACCESS_KEY", "secret"),
    _v("VORNEQ_AI_IMAGE_UI_ENABLED", "flag", "staging"),
    _v("VORNEQ_AI_IMAGE_ALLOWED_USER_IDS", "allowlist", "staging"),
    _v("VORNEQ_AI_IMAGE_AUTHORIZED_SHA", "pin", "staging"),
    _v("VORNEQ_AI_IMAGE_OWNER_AUTH", "reference", "staging"),
    _v("VORNEQ_AI_IMAGE_STAGING_PREPAID_ONLY", "flag", "staging"),
    _v("VORNEQ_AI_IMAGE_WORKER_SERVICE_ID", "host", "staging"),
    _v("VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED", "flag", "staging"),
    _v("VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH", "reference", "staging"),
    _v("VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED", "flag", "production"),
    _v("VORNEQ_AI_IMAGE_PRODUCTION_ENABLED", "flag", "production"),
    _v("VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET", "flag", "production"),
    _v("VORNEQ_AI_IMAGE_PRODUCTION_AUTHORIZED_SHA", "pin", "production"),
    _v("VORNEQ_AI_IMAGE_PRODUCTION_OWNER_AUTH", "reference", "production"),
    _v("VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS", "allowlist", "production"),
    # Sprache
    _v("VORNEQ_AI_VOICE_ENABLED", "flag", parity="staging_first"),
    _v("VORNEQ_AI_VOICE_PROVIDER", "config", parity="staging_first"),
    _v("VORNEQ_AI_VOICE_PAID_CALLS_ENABLED", "flag", parity="allowed_difference"),
    _v("VORNEQ_AI_VOICE_SESSION_TTL_SECONDS", "config", parity="allowed_difference"),
    _v("VORNEQ_AI_VOICE_ALLOWED_USER_IDS", "allowlist"),
    # Nur Werkzeuge / Tests (nie in Render erwartet)
    _v("VORNEQ_ALLOW_INSPECT_STAGING_SMOKE", "tooling", "local"),
    _v("VORNEQ_ALLOW_INSPECT_MIGRATION_PREFLIGHT", "tooling", "local"),
    _v("VORNEQ_ALLOW_STAGING_SEED", "tooling", "local"),
    _v("VORNEQ_EXPECTED_STAGING_DATABASE", "tooling", "local"),
    _v("VORNEQ_EXPECTED_STAGING_DB_HOST", "tooling", "local"),
    _v("VORNEQ_EXPECTED_STAGING_DB_PORT", "tooling", "local"),
    _v("VORNEQ_EXPECTED_STAGING_DB_USER", "tooling", "local"),
    _v("VORNEQ_FIXTURE_CLEANUP_LOCAL_TEST", "tooling", "local"),
    _v("VORNEQ_QUARANTINE_CI_DB_TEST_MODE", "tooling", "local"),
    _v("VORNEQ_QUARANTINE_LOCAL_ONLY", "tooling", "local"),
)
CATALOG_BY_NAME = {item.name: item for item in CATALOG}
assert len(CATALOG_BY_NAME) == len(CATALOG), "doppelte Katalogeinträge"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def _flag_value(raw):
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    return "INVALID"


def _allowlist_count(raw):
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if any(not p.isdecimal() for p in parts):
        return "INVALID"
    return len(set(parts))


def _ids(raw):
    if not isinstance(raw, str):
        return set()
    return {int(p) for p in raw.split(",") if p.strip().isdecimal()}


def describe_variable(var: Var, environ, release):
    raw = environ.get(var.name)
    entry = {"kind": var.kind, "scope": var.scope, "parity": var.parity}
    if raw is None:
        entry["state"] = "MISSING"
        return entry
    entry["state"] = "PRESENT"
    if var.kind == "flag":
        entry["value"] = _flag_value(raw)
    elif var.kind == "pin":
        value = raw.strip().lower()
        if not _SHA.fullmatch(value):
            entry["value"] = "INVALID"
        elif release and value == release:
            entry["value"] = "MATCHES_RELEASE"
        else:
            entry["value"] = "MISMATCH"
    elif var.kind == "allowlist":
        entry["value"] = _allowlist_count(raw)
    elif var.kind in ("config", "host", "runtime"):
        if var.name == "RENDER_GIT_COMMIT":
            entry["value"] = raw.strip().lower() if _SHA.fullmatch(raw.strip().lower()) else "INVALID"
        else:
            entry["value"] = raw.strip()[:200]
    # secret / reference / tooling: nur Zustand
    return entry


# --------------------------------------------------------------------------
# Snapshot
# --------------------------------------------------------------------------

def _section(report, name, builder):
    try:
        report[name] = builder()
    except Exception as exc:  # noqa: BLE001 – fail-closed, ohne Details/Secrets
        report[name] = {"error": type(exc).__name__}
        report["errors"].append(name)


def _release(environ):
    for name in ("VORNEQ_RELEASE", "RENDER_GIT_COMMIT"):
        value = (environ.get(name) or "").strip().lower()
        if _SHA.fullmatch(value):
            return value
    return None


def _settings_section():
    from django.conf import settings

    templates = settings.TEMPLATES[0]
    options = templates.get("OPTIONS", {})
    caches = getattr(settings, "CACHES", {})
    storages = getattr(settings, "STORAGES", {})
    return {
        "vorneq_env": getattr(settings, "VORNEQ_ENV", None),
        "debug": bool(settings.DEBUG),
        "root_urlconf": settings.ROOT_URLCONF,
        "settings_module": os.environ.get("DJANGO_SETTINGS_MODULE"),
        "installed_apps": list(settings.INSTALLED_APPS),
        "middleware": list(settings.MIDDLEWARE),
        "context_processors": list(options.get("context_processors", [])),
        "template_loaders": [str(item) for item in options.get("loaders", [])] or ["APP_DIRS" if templates.get("APP_DIRS") else "DEFAULT"],
        "database_routers": list(getattr(settings, "DATABASE_ROUTERS", [])),
        "database_aliases": sorted(settings.DATABASES),
        "database_engines": {alias: cfg.get("ENGINE") for alias, cfg in sorted(settings.DATABASES.items())},
        "cache_backend": caches.get("default", {}).get("BACKEND"),
        "storages": {name: cfg.get("BACKEND") for name, cfg in sorted(storages.items())},
        "languages": [code for code, _label in settings.LANGUAGES],
        "language_code": settings.LANGUAGE_CODE,
        "allowed_hosts": list(settings.ALLOWED_HOSTS),
        "csrf_trusted_origins": list(getattr(settings, "CSRF_TRUSTED_ORIGINS", [])),
        "account_email_verification": getattr(settings, "ACCOUNT_EMAIL_VERIFICATION", None),
    }


def _registry_section():
    from django.urls import NoReverseMatch, reverse
    from django.utils import translation

    from apps.platform_shell.registry import registry

    items = []
    with translation.override("en"):
        for manifest in registry.all():
            try:
                reverse(manifest.url_name)
                reversible = True
            except NoReverseMatch:
                reversible = False
            items.append({
                "slug": manifest.slug,
                "url_name": manifest.url_name,
                "order": manifest.order,
                "show_in_primary_nav": manifest.show_in_primary_nav,
                "requires_authentication": manifest.requires_authentication,
                "capabilities": list(manifest.capabilities),
                "reversible": reversible,
            })
    return {"apps": items, "problems": [i["slug"] for i in items if not i["reversible"]]}


def _urls_section():
    from django.urls import get_resolver
    from django.urls.resolvers import URLResolver

    names, patterns = set(), []

    def walk(entries, prefix="", namespace=""):
        for entry in entries:
            if isinstance(entry, URLResolver):
                ns = namespace
                if entry.namespace:
                    ns = f"{namespace}{entry.namespace}:"
                walk(entry.url_patterns, prefix + str(entry.pattern), ns)
            else:
                patterns.append(prefix + str(entry.pattern))
                if entry.name:
                    names.add(namespace + entry.name)

    walk(get_resolver().url_patterns)
    joined = "\n".join(sorted(set(patterns)))
    return {
        "pattern_count": len(set(patterns)),
        "named_routes": sorted(names),
        "patterns_sha256": hashlib.sha256(joined.encode()).hexdigest(),
    }


def _migrations_section():
    from django.db import connections, router
    from django.db.migrations.loader import MigrationLoader

    result = {}
    for alias in sorted(connections.databases):
        connection = connections[alias]
        try:
            loader = MigrationLoader(connection, ignore_no_migrations=True)
        except Exception as exc:  # noqa: BLE001 – je Alias fail-closed, ohne Details
            result[alias] = {"error": type(exc).__name__}
            continue

        def routed(key, alias=alias):
            # Nur Apps, die laut Router in diese Datenbank migriert werden.
            return router.allow_migrate(alias, key[0]) is not False

        applied = {k for k in loader.applied_migrations if routed(k)}
        on_disk = {k for k in loader.disk_migrations if routed(k)}
        graph_nodes = {k for k in loader.graph.nodes if routed(k)}
        result[alias] = {
            "applied_count": len(applied),
            "on_disk_count": len(on_disk),
            "unapplied": sorted(f"{a}.{n}" for a, n in graph_nodes - applied),
            "applied_not_on_disk": sorted(f"{a}.{n}" for a, n in applied - on_disk),
            "conflicts": {app: sorted(names) for app, names in loader.detect_conflicts().items()},
        }
    return result


def _system_data_section():
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.sites.models import Site

    return {
        "sites": [{"id": s.pk, "domain": s.domain} for s in Site.objects.order_by("pk")],
        "groups": sorted(Group.objects.values_list("name", flat=True)),
        "permission_count": Permission.objects.count(),
        "content_type_count": ContentType.objects.count(),
    }


def _accounts_section(environ):
    """Rollen und Bindungen privilegierter Konten – ohne Namen/E-Mails."""
    from django.contrib.auth import get_user_model

    from apps.core.models import Identity, UserIdentity

    try:
        from allauth.account.models import EmailAddress
    except Exception:  # noqa: BLE001
        EmailAddress = None

    User = get_user_model()
    allowlists = {
        "ai_staging": _ids(environ.get("VORNEQ_AI_STAGING_ALLOWED_USER_IDS", "")),
        "ai_production": _ids(environ.get("VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS", "")),
        "conversations": _ids(environ.get("VORNEQ_AI_CONVERSATIONS_ALLOWED_USER_IDS", "")),
        "image_staging": _ids(environ.get("VORNEQ_AI_IMAGE_ALLOWED_USER_IDS", "")),
        "image_production": _ids(environ.get("VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS", "")),
        "voice": _ids(environ.get("VORNEQ_AI_VOICE_ALLOWED_USER_IDS", "")),
    }
    privileged = User.objects.filter(is_staff=True) | User.objects.filter(is_superuser=True)
    accounts = []
    for user in privileged.distinct().order_by("pk"):
        binding = UserIdentity.objects.filter(user=user).select_related("identity").first()
        verified_primary = None
        if EmailAddress is not None:
            verified_primary = EmailAddress.objects.filter(user=user, primary=True, verified=True).exists()
        accounts.append({
            "pk": user.pk,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "groups": sorted(user.groups.values_list("name", flat=True)),
            "direct_permission_count": user.user_permissions.count(),
            "verified_primary_email": verified_primary,
            "identity_bound": binding is not None,
            "identity_active_human": bool(
                binding and binding.identity.is_active and binding.identity.kind == Identity.Kind.HUMAN
            ),
            "allowlisted": sorted(name for name, ids in allowlists.items() if user.pk in ids),
        })
    return {
        "user_count": User.objects.count(),
        "active_user_count": User.objects.filter(is_active=True).count(),
        "bound_identity_count": UserIdentity.objects.count(),
        "privileged_accounts": accounts,
    }


def _bool_setting(name, default=False):
    from django.conf import settings

    return getattr(settings, name, default) is True


def _capabilities_section(environ, release):
    """Statische Gate-Prädikate je Funktion (ohne Netzwerk, ohne Kosten)."""
    from django.conf import settings

    env = getattr(settings, "VORNEQ_ENV", None)
    service = environ.get("RENDER_SERVICE_ID")
    debug_off = settings.DEBUG is False
    stop_clear = not _bool_setting("VORNEQ_AI_EMERGENCY_STOP")

    def release_predicate(pin_name, follow_name):
        if _bool_setting(follow_name):
            return "NOT_VERIFIED"  # benötigt GitHub-Deployment-Prüfung (Netzwerk)
        pin = (environ.get(pin_name) or "").strip().lower()
        return bool(release and pin == release)

    def state(predicates):
        values = list(predicates.values())
        if any(v is False for v in values):
            return "DISABLED"
        if any(v == "NOT_VERIFIED" for v in values):
            return "NOT_VERIFIED"
        return "ENABLED"

    caps = {}
    if env == "staging":
        chat = {
            "environment": True, "debug_off": debug_off, "emergency_stop_clear": stop_clear,
            "service_identity": service == STAGING_SERVICE_ID,
            "trial_flag": _bool_setting("VORNEQ_AI_STAGING_TRIAL_ENABLED"),
            "ai_core_flag": _bool_setting("VORNEQ_AI_CORE_ENABLED"),
            "phase_b_flag": _bool_setting("VORNEQ_AI_PHASE_B_ENABLED"),
            "release": release_predicate("VORNEQ_AI_STAGING_AUTHORIZED_SHA", "VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS"),
            "owner_reference": bool(environ.get("VORNEQ_AI_STAGING_OWNER_AUTH")),
            "model_matches": bool(environ.get("VORNEQ_AI_STAGING_APPROVED_MODEL"))
            and environ.get("VORNEQ_AI_STAGING_APPROVED_MODEL") == environ.get("VORNEQ_AI_PHASE_B_MODEL"),
            "provider_key": bool(environ.get("OPENAI_API_KEY")),
            "actor_allowlist": bool(_ids(environ.get("VORNEQ_AI_STAGING_ALLOWED_USER_IDS", ""))),
        }
        image_ui = {
            "environment": True, "debug_off": debug_off,
            "ui_flag": _bool_setting("VORNEQ_AI_IMAGE_UI_ENABLED"),
            "actor_allowlist": bool(_ids(environ.get("VORNEQ_AI_IMAGE_ALLOWED_USER_IDS", ""))),
        }
        recovery_flag = _bool_setting("VORNEQ_AI_CHAT_RECOVERY_ENABLED")
    elif env == "production":
        chat = {
            "environment": True, "debug_off": debug_off, "emergency_stop_clear": stop_clear,
            "service_identity": service == PRODUCTION_SERVICE_ID,
            "production_flag": _bool_setting("VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED"),
            "recovery_flag": _bool_setting("VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED"),
            "release": release_predicate("VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA", "VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS"),
            "owner_reference": bool(environ.get("VORNEQ_AI_PRODUCTION_OWNER_AUTH")),
            "model_matches": bool(environ.get("VORNEQ_AI_PRODUCTION_APPROVED_MODEL"))
            and environ.get("VORNEQ_AI_PRODUCTION_APPROVED_MODEL") == environ.get("VORNEQ_AI_PHASE_B_MODEL"),
            "provider_key": bool(environ.get("OPENAI_API_KEY")),
            "ledger_flag": _bool_setting("VORNEQ_AI_LEDGER_ENABLED"),
            "actor_policy": (environ.get("VORNEQ_AI_PRODUCTION_ACTOR_POLICY") or "allowlist") == "authenticated"
            or bool(_ids(environ.get("VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS", ""))),
        }
        image_ui = {
            "environment": True, "debug_off": debug_off,
            "ui_flag": _bool_setting("VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED"),
            "service_identity": service == PRODUCTION_SERVICE_ID,
        }
        recovery_flag = _bool_setting("VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED")
    else:
        chat = {"environment": False}
        image_ui = {"environment": False}
        recovery_flag = False

    caps["ai_chat"] = {"state": state(chat), "predicates": chat}
    caps["ai_image_studio_ui"] = {"state": state(image_ui), "predicates": image_ui}
    shared = {
        "ai_conversations": "VORNEQ_AI_CONVERSATIONS_ENABLED",
        "ai_context_retrieval": "VORNEQ_AI_CONTEXT_RETRIEVAL_ENABLED",
        "ai_response_v3": "VORNEQ_AI_RESPONSE_V3_ENABLED",
        "ai_response_v3_stage2": "VORNEQ_AI_RESPONSE_V3_STAGE2_ENABLED",
        "ai_voice": "VORNEQ_AI_VOICE_ENABLED",
        "ai_image_generation": "VORNEQ_AI_IMAGE_ENABLED",
        "ai_ledger": "VORNEQ_AI_LEDGER_ENABLED",
    }
    for cap, name in shared.items():
        caps[cap] = {"state": "ENABLED" if _bool_setting(name) else "DISABLED", "predicates": {name: _bool_setting(name)}}
    caps["ai_chat_recovery"] = {"state": "ENABLED" if recovery_flag else "DISABLED", "predicates": {"flag": recovery_flag}}
    caps["ai_emergency_stop"] = {"state": "ACTIVE" if not stop_clear else "CLEAR", "predicates": {}}
    return caps


def build_snapshot(environ=None, include_database=True):
    environ = dict(os.environ if environ is None else environ)
    release = _release(environ)
    report = {
        "snapshot_version": SNAPSHOT_VERSION,
        "release": release,
        "errors": [],
    }
    _section(report, "settings", _settings_section)
    report["environment"] = report["settings"].get("vorneq_env") if isinstance(report["settings"], dict) else None
    _section(report, "variables", lambda: {
        var.name: describe_variable(var, environ, release) for var in CATALOG
    })
    _section(report, "uncatalogued_vorneq_variables", lambda: sorted(
        name for name in environ
        if (name.startswith("VORNEQ_") or name.startswith("DJANGO_")) and name not in CATALOG_BY_NAME
        and name != "DJANGO_SETTINGS_MODULE" and name != "VORNEQ_RELEASE"
    ))
    _section(report, "platform_registry", _registry_section)
    _section(report, "urls", _urls_section)
    _section(report, "capabilities", lambda: _capabilities_section(environ, release))
    if include_database:
        _section(report, "migrations", _migrations_section)
        if isinstance(report.get("migrations"), dict):
            report["errors"].extend(
                f"migrations.{alias}" for alias, data in report["migrations"].items()
                if isinstance(data, dict) and "error" in data
            )
        _section(report, "system_data", _system_data_section)
        _section(report, "accounts", lambda: _accounts_section(environ))
    report["status"] = "INVALID" if report["errors"] or not release and report["environment"] in ("staging", "production") else "COMPLETE"
    if report["status"] == "INVALID" and not report["errors"]:
        report["errors"].append("release_unknown")
    return report


# --------------------------------------------------------------------------
# Vergleich
# --------------------------------------------------------------------------

STRUCTURE_KEYS = (
    "installed_apps", "middleware", "context_processors", "template_loaders",
    "database_routers", "database_aliases", "languages", "language_code", "root_urlconf",
)
ALLOWED_SETTING_KEYS = ("allowed_hosts", "csrf_trusted_origins", "vorneq_env")


def _finding(group, area, item, staging, production, note):
    return {"group": group, "area": area, "item": item, "staging": staging,
            "production": production, "note": note}


def compare_snapshots(staging, production):
    """Gruppen: A unnötig, B erlaubt, C Staging zuerst, D Architektur, NV nicht prüfbar."""
    findings = []
    invalid = []
    for label, snap in (("staging", staging), ("production", production)):
        if snap.get("snapshot_version") != SNAPSHOT_VERSION:
            invalid.append(f"{label}: snapshot_version")
        if snap.get("status") != "COMPLETE":
            invalid.append(f"{label}: status {snap.get('status')}")
    if staging.get("environment") != "staging" or production.get("environment") != "production":
        invalid.append("environment labels")
    same_release = staging.get("release") and staging.get("release") == production.get("release")
    if not same_release:
        findings.append(_finding("C", "release", "release", staging.get("release"), production.get("release"),
                                 "Unterschiedliche Releases; Strukturvergleich nur eingeschränkt aussagekräftig."))

    s_set, p_set = staging.get("settings", {}), production.get("settings", {})
    for key in STRUCTURE_KEYS:
        if s_set.get(key) != p_set.get(key):
            findings.append(_finding("A" if same_release else "C", "settings", key, s_set.get(key), p_set.get(key),
                                     "Strukturelle Einstellung weicht ab."))
    for key in ("debug", "cache_backend", "storages", "database_engines", "account_email_verification"):
        if s_set.get(key) != p_set.get(key):
            findings.append(_finding("A", "settings", key, s_set.get(key), p_set.get(key),
                                     "Laufzeitverhalten weicht ab."))
    for key in ALLOWED_SETTING_KEYS:
        if s_set.get(key) != p_set.get(key):
            findings.append(_finding("B", "settings", key, s_set.get(key), p_set.get(key), "Umgebungsspezifisch."))

    s_reg = {a["slug"]: a for a in staging.get("platform_registry", {}).get("apps", [])}
    p_reg = {a["slug"]: a for a in production.get("platform_registry", {}).get("apps", [])}
    for slug in sorted(set(s_reg) | set(p_reg)):
        if s_reg.get(slug) != p_reg.get(slug):
            group = "A" if slug in p_reg and slug not in s_reg else "C" if slug in s_reg and slug not in p_reg else "A"
            findings.append(_finding(group, "platform_registry", slug, s_reg.get(slug), p_reg.get(slug),
                                     "App-Registrierung weicht ab."))
    for label, snap in (("staging", staging), ("production", production)):
        for slug in snap.get("platform_registry", {}).get("problems", []):
            findings.append(_finding("D", "platform_registry", slug, label == "staging", label == "production",
                                     f"Manifest in {label} nicht auflösbar."))

    s_urls, p_urls = staging.get("urls", {}), production.get("urls", {})
    if s_urls.get("patterns_sha256") != p_urls.get("patterns_sha256"):
        missing = sorted(set(p_urls.get("named_routes", [])) - set(s_urls.get("named_routes", [])))
        extra = sorted(set(s_urls.get("named_routes", [])) - set(p_urls.get("named_routes", [])))
        findings.append(_finding("A" if missing else "C", "urls", "patterns", {"only_staging": extra},
                                 {"only_production": missing}, "URL-Inventar weicht ab."))

    for label, snap in (("staging", staging), ("production", production)):
        for alias, data in (snap.get("migrations") or {}).items():
            if not isinstance(data, dict):
                continue
            if data.get("unapplied"):
                findings.append(_finding("A", "migrations", f"{alias}.unapplied",
                                         data["unapplied"] if label == "staging" else None,
                                         data["unapplied"] if label == "production" else None,
                                         f"Nicht angewendete Migrationen in {label} (Anwendung nur mit Owner-Freigabe)."))
            if data.get("conflicts"):
                findings.append(_finding("D", "migrations", f"{alias}.conflicts", label, label, "Migrationskonflikt."))
            if data.get("applied_not_on_disk"):
                findings.append(_finding("D", "migrations", f"{alias}.applied_not_on_disk",
                                         data["applied_not_on_disk"] if label == "staging" else None,
                                         data["applied_not_on_disk"] if label == "production" else None,
                                         "Angewendet, aber nicht im Code vorhanden."))

    s_sys, p_sys = staging.get("system_data", {}), production.get("system_data", {})
    if s_sys.get("groups") != p_sys.get("groups"):
        findings.append(_finding("A", "system_data", "groups", s_sys.get("groups"), p_sys.get("groups"),
                                 "Gruppen weichen ab (System-Seed)."))
    for key in ("permission_count", "content_type_count"):
        if s_sys.get(key) != p_sys.get(key):
            findings.append(_finding("A" if same_release else "C", "system_data", key, s_sys.get(key), p_sys.get(key),
                                     "Systemdaten weichen ab."))
    if s_sys.get("sites") != p_sys.get("sites"):
        findings.append(_finding("B", "system_data", "sites", s_sys.get("sites"), p_sys.get("sites"), "Domain je Umgebung."))

    s_caps, p_caps = staging.get("capabilities", {}), production.get("capabilities", {})
    for cap in sorted(set(s_caps) | set(p_caps)):
        s_state = (s_caps.get(cap) or {}).get("state")
        p_state = (p_caps.get(cap) or {}).get("state")
        if s_state == p_state:
            continue
        if cap == "ai_emergency_stop":
            group, note = "B", "Not-Aus ist je Umgebung unabhängig."
        elif "NOT_VERIFIED" in (s_state, p_state):
            group, note = "NV", "Release-Prüfung erfordert Netzwerk (Follow-Owner-Deployments)."
        elif p_state == "ENABLED":
            group, note = "A", "In Production aktiv, in Staging nicht: Staging muss mindestens Production entsprechen."
        else:
            group, note = "C", "In Staging aktiv, in Production nicht (Staging zuerst)."
        findings.append(_finding(group, "capabilities", cap, s_state, p_state, note))

    s_vars, p_vars = staging.get("variables", {}), production.get("variables", {})
    for name in sorted(set(s_vars) | set(p_vars)):
        var = CATALOG_BY_NAME.get(name)
        s_v, p_v = s_vars.get(name, {}), p_vars.get(name, {})
        if var is None or var.parity == "informational" or var.scope == "local":
            continue
        s_cmp = (s_v.get("state"), s_v.get("value"))
        p_cmp = (p_v.get("state"), p_v.get("value"))
        if var.scope == "staging":
            if p_v.get("state") == "PRESENT" and var.kind == "flag" and p_v.get("value") is True:
                findings.append(_finding("D", "variables", name, s_cmp, p_cmp,
                                         "Staging-Variable ist in Production gesetzt (wirkungslos oder verwirrend)."))
            continue
        if var.scope == "production":
            if s_v.get("state") == "PRESENT" and var.kind == "flag" and s_v.get("value") is True:
                findings.append(_finding("D", "variables", name, s_cmp, p_cmp,
                                         "Production-Variable ist in Staging gesetzt (wirkungslos oder verwirrend)."))
            continue
        if s_cmp == p_cmp:
            continue
        if var.parity == "must_match":
            group = "A"
        elif var.parity == "staging_first":
            group = "A" if (p_v.get("value") is True and s_v.get("value") is not True) else "C"
        else:
            group = "B"
        findings.append(_finding(group, "variables", name, s_cmp, p_cmp, f"kind={var.kind}"))

    for label, snap in (("staging", staging), ("production", production)):
        for name in snap.get("uncatalogued_vorneq_variables", []):
            findings.append(_finding("D", "variables", name, label == "staging", label == "production",
                                     f"In {label} gesetzt, aber nicht im Katalog/Code (veraltet?)."))

    findings.extend(_compare_accounts(staging.get("accounts", {}), production.get("accounts", {})))

    groups = {}
    for item in findings:
        groups[item["group"]] = groups.get(item["group"], 0) + 1
    status = "INVALID" if invalid else ("DRIFT" if groups.get("A") or groups.get("D") else "PARITY")
    return {"status": status, "invalid": invalid, "summary": groups, "findings": findings}


def _role_profile(accounts):
    profile = set()
    for acc in accounts.get("privileged_accounts", []) or []:
        if not acc.get("is_active"):
            continue
        ready = bool(acc.get("identity_active_human") and acc.get("verified_primary_email"))
        role = "superuser" if acc.get("is_superuser") else "staff"
        profile.add((role, ready, tuple(sorted(
            name.replace("_staging", "").replace("_production", "") for name in acc.get("allowlisted", [])
        ))))
    return profile


def _compare_accounts(staging_accounts, production_accounts):
    findings = []
    s_prof, p_prof = _role_profile(staging_accounts), _role_profile(production_accounts)
    for role, ready, lists in sorted(p_prof - s_prof):
        findings.append(_finding("A", "accounts", f"{role}:{'ready' if ready else 'not_ready'}:{','.join(lists) or '-'}",
                                 None, {"role": role, "identity_and_verified_email": ready, "allowlists": lists},
                                 "Production hat ein Admin-Profil, das in Staging fehlt (Rolle, Identity, "
                                 "verifizierte E-Mail, Allowlists). Behebung nur durch den Eigentümer."))
    for role, ready, lists in sorted(s_prof - p_prof):
        findings.append(_finding("C", "accounts", f"{role}:{'ready' if ready else 'not_ready'}:{','.join(lists) or '-'}",
                                 {"role": role, "identity_and_verified_email": ready, "allowlists": lists}, None,
                                 "Nur in Staging vorhandenes Admin-Profil."))
    return findings


def dumps(report):
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, default=str)
