"""Operator-only, observational diagnostics. Never authorizes a request.

Only explicit verify=True may contact GitHub's deployment evidence API.
No provider, database queries, cache writes, or arbitrary values in output.
"""
import os

from django.conf import settings

from apps.ai_core import deploy_authorization as proof
from apps.ai_core import production_policy, staging_policy, request_recovery
from apps.ai_core.image_generation import policy as image
from apps.ai_core.provider_resolution import Capability, legacy_model_matches
from apps.ai_ledger.service import ledger_enabled


def _flag(name):
    return bool(getattr(settings, name, False))


def _matches(pattern, value):
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def _official_reason(environment, verify):
    token = os.environ.get("VORNEQ_AI_DEPLOY_READ_TOKEN", "")
    if not token:
        return "DEPLOY_READ_TOKEN_MISSING"
    if not verify:
        return "NOT_VERIFIED"
    try:
        return proof._deployment_reason(
            environment, os.environ.get("RENDER_GIT_COMMIT", ""), token
        )
    except proof.DeploymentDrift:
        return "DEPLOYMENT_SHA_OR_ENVIRONMENT_DRIFT"
    except Exception:
        return "DEPLOYMENT_EVIDENCE_UNAVAILABLE"


def _release_reason(environment, pin, follow, official):
    live = os.environ.get("RENDER_GIT_COMMIT", "")
    if not follow:
        return "VERIFIED" if _matches(proof.SHA, pin) and pin == live else "LEGACY_SHA_MISMATCH"
    if (settings.VORNEQ_ENV != environment or settings.DEBUG is not False
            or os.environ.get("RENDER_SERVICE_ID") != proof.SERVICES[environment]
            or not _matches(proof.SHA, live)):
        return "INVALID_RELEASE_IDENTITY"
    return official()


def _result(checks, release=None):
    reasons = [reason for ok, reason in checks if not ok]
    if release not in (None, "VERIFIED"):
        reasons.append(release)
    return {
        "status": ("BLOCKED" if any(r != "NOT_VERIFIED" for r in reasons)
                   else "NOT_VERIFIED" if reasons else "CONFIGURATION_READY"),
        "reasons": reasons,
        "release_evidence": release if release is not None else "NOT_APPLICABLE",
        "actor_access": "NOT_VERIFIED",
        "provider_delivery": "NOT_VERIFIED",
    }


def _chat_checks(environment):
    staging = environment == "staging"
    prefix = "VORNEQ_AI_STAGING" if staging else "VORNEQ_AI_PRODUCTION"
    owner_pattern = staging_policy._OWNER_REF if staging else production_policy._OWNER_REF
    owner = getattr(settings, prefix + "_OWNER_AUTH", "")
    model = getattr(settings, prefix + "_APPROVED_MODEL", "")
    checks = [
        (not _flag("VORNEQ_AI_EMERGENCY_STOP"), "EMERGENCY_STOP_ACTIVE"),
        (settings.DEBUG is False, "DEBUG_ENABLED"),
        (os.environ.get("RENDER_SERVICE_ID") == proof.SERVICES[environment], "WRONG_SERVICE"),
        (_matches(owner_pattern, owner), "OWNER_AUTH_INVALID"),
        (isinstance(model, str) and bool(model) and len(model) <= 100
         and legacy_model_matches("openai-text", Capability.TEXT,
                                  os.environ.get("VORNEQ_AI_PHASE_B_MODEL", ""), (model,)),
         "APPROVED_MODEL_MISMATCH"),
        (bool(os.environ.get("OPENAI_API_KEY", "")), "TEXT_KEY_MISSING"),
    ]
    if staging:
        checks += [
            (_flag("VORNEQ_AI_STAGING_TRIAL_ENABLED"), "STAGING_TRIAL_DISABLED"),
            (_flag("VORNEQ_AI_CORE_ENABLED"), "AI_CORE_DISABLED"),
            (_flag("VORNEQ_AI_PHASE_B_ENABLED"), "PHASE_B_DISABLED"),
            (bool(staging_policy._ids_from_setting()), "CHAT_ALLOWLIST_INVALID"),
        ]
        if not _flag("VORNEQ_AI_STAGING_UNMETERED"):
            cap = getattr(settings, "VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD", 0)
            reserve = getattr(settings, "VORNEQ_AI_STAGING_RESERVE_MICROUSD", 0)
            requests = getattr(settings, "VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS", 0)
            checks.append((type(cap) is int and type(reserve) is int and type(requests) is int
                           and 1 <= requests <= 5 and 1_000 <= reserve <= 100_000
                           and reserve <= cap <= 250_000 and cap >= reserve * requests,
                           "STAGING_BUDGET_CONFIG_INVALID"))
    else:
        checks += [
            (_flag("VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED"), "PRODUCTION_CHAT_DISABLED"),
            (request_recovery.enabled(), "PRODUCTION_RECOVERY_DISABLED"),
            (ledger_enabled(), "LEDGER_CONFIG_INVALID"),
        ]
    return checks, getattr(settings, prefix + "_AUTHORIZED_SHA", "")


def _image_checks():
    provider = getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "")
    checks = [
        (_flag("VORNEQ_AI_IMAGE_ENABLED"), "IMAGE_DISABLED"),
        (_flag("VORNEQ_AI_IMAGE_UI_ENABLED"), "IMAGE_UI_DISABLED"),
        (not _flag("VORNEQ_AI_EMERGENCY_STOP"), "EMERGENCY_STOP_ACTIVE"),
        (settings.DEBUG is False, "DEBUG_ENABLED"),
        (os.environ.get("RENDER_SERVICE_ID") == proof.SERVICES["staging"], "WRONG_SERVICE"),
        (provider in ("mock", "openai"), "IMAGE_PROVIDER_INVALID"),
        (_matches(image._OWNER, getattr(settings, "VORNEQ_AI_IMAGE_OWNER_AUTH", "")),
         "IMAGE_OWNER_AUTH_INVALID"),
        (bool(image._ids()), "IMAGE_ALLOWLIST_INVALID"),
    ]
    if provider == "openai":
        # The existing policy helper only validates configuration; no SDK or storage call.
        try:
            paid_ready = image._paid_controls_ready()
        except Exception:
            paid_ready = False
        checks.append((paid_ready, "IMAGE_PAID_CONTROLS_NOT_READY"))
    return checks, provider


def build_report(environment, *, verify=False):
    if environment not in proof.SERVICES or settings.VORNEQ_ENV != environment:
        raise ValueError("INVALID_ENVIRONMENT")

    # Share a single fresh evidence observation across capabilities. Do not
    # touch the authorization cache; its TTL may make live observations differ.
    observed = []

    def official():
        if not observed:
            observed.append(_official_reason(environment, verify))
        return observed[0]

    chat_checks, chat_pin = _chat_checks(environment)
    chat_release = _release_reason(
        environment, chat_pin, getattr(settings, "VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS", False) is True, official
    )
    chat_page = _result(chat_checks, chat_release)
    global_checks = list(chat_checks)
    if environment == "staging":
        global_checks.append((_flag("VORNEQ_GLOBAL_AI_ENABLED"), "GLOBAL_AI_DISABLED"))
    if environment == "staging":
        image_checks, provider = _image_checks()
        image_release = _release_reason(
            environment, getattr(settings, "VORNEQ_AI_IMAGE_AUTHORIZED_SHA", ""),
            provider == "openai" and getattr(settings, "VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS", False) is True,
            official,
        )
        studio = _result(image_checks, image_release)
    else:
        # Production Studio is an independent read-only preview. Release
        # evidence, chat authorization and paid image policy do not grant it.
        studio = _result([
            (getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED", False) is True,
             "PRODUCTION_IMAGE_PREVIEW_DISABLED"),
            (settings.DEBUG is False, "DEBUG_ENABLED"),
            (os.environ.get("RENDER_SERVICE_ID") == proof.SERVICES["production"], "WRONG_SERVICE"),
        ])
        studio["mode"] = "READ_ONLY_PREVIEW"

    return {
        "environment": environment,
        "evidence_mode": "FRESH_GITHUB_READ" if verify else "OFFLINE",
        "chat_page": chat_page,
        "global_chat": _result(global_checks, chat_release),
        "image_studio": studio,
        "note": "CONFIGURATION_READY is not actor authorization, worker health or paid-call permission.",
    }
