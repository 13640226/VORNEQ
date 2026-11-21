"""Durable DB-backed image queue. Redis only signals wake-up; DB is truth."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone

from apps.ai_core.models import AIImageDailyQuota, AIImageJob
from .policy import (
    SIZES, actor_allowed, enabled, paid_provider_enabled, paid_worker_enabled, worker_enabled,
)
from .providers import ImageProviderError, MockImageProvider, OpenAIImageProvider
from .storage import image_storage, store_image


class ImageQueueError(Exception):
    pass


def _limit(name, ceiling):
    value = getattr(settings, name, 0)
    if type(value) is not int or not 1 <= value <= ceiling:
        raise ImageQueueError("invalid image quota")
    return value


def submit_image_job(user, *, request_id: uuid.UUID, prompt: str, size: str):
    if not actor_allowed(user):
        raise PermissionError("image capability disabled or unauthorized")
    if type(request_id) is not uuid.UUID or request_id.version != 4:
        raise ImageQueueError("invalid request id")
    if not isinstance(prompt, str) or not 4 <= len(prompt) <= 2000:
        raise ImageQueueError("invalid prompt")
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in prompt):
        raise ImageQueueError("invalid prompt")
    if size not in SIZES:
        raise ImageQueueError("invalid image size")
    provider = getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "")
    model = getattr(settings, "VORNEQ_AI_IMAGE_MODEL", "")
    if provider == "openai" and not paid_provider_enabled():
        raise PermissionError("paid image capability disabled")
    if provider == "mock":
        model = "mock"
    if provider not in ("mock", "openai"):
        raise PermissionError("image provider disabled")
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    day = datetime.now(dt_timezone.utc).date()
    first = datetime.combine(day, datetime.min.time(), tzinfo=dt_timezone.utc)
    now = timezone.now()
    with transaction.atomic():
        # One global row lock serializes requests and quota accounting among actors.
        quota, _ = AIImageDailyQuota.objects.get_or_create(day_utc=day)
        AIImageDailyQuota.objects.select_for_update().get(pk=quota.pk)
        existing = AIImageJob.objects.filter(pk=request_id).first()
        if existing:
            if (existing.owner_id != user.pk or existing.prompt_digest != digest
                    or existing.image_size != size):
                raise ImageQueueError("request id conflict")
            return existing, False
        if quota.submitted >= _limit("VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS", 500):
            raise ImageQueueError("global image daily cap")
        today_count = AIImageJob.objects.filter(owner=user, created_at__gte=first).count()
        if today_count >= _limit("VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS", 50):
            raise ImageQueueError("user image daily cap")
        # One submission per minute, per user; no token/cache rate-limit bypass.
        recent = AIImageJob.objects.filter(owner=user, created_at__gte=now-timedelta(seconds=60))
        if recent.exists():
            raise ImageQueueError("image request rate limit")
        job = AIImageJob.objects.create(
            pk=request_id, owner=user, prompt=prompt, prompt_digest=digest,
            model_id=model, image_size=size, provider=provider,
        )
        quota.submitted += 1
        quota.save(update_fields=["submitted"])
    # A Redis cache notification is advisory; worker always polls PostgreSQL.
    try:
        cache.set("vorneq:image-queue:wakeup", "1", timeout=30)
    except Exception:
        pass
    return job, True


def serialize_job(job):
    """Never expose original prompts, secrets, raw errors, or storage object keys."""
    result = {
        "id": str(job.pk),
        "status": job.status,
        "model": job.model_id,
        "size": job.image_size,
        "label": "AI-generated (mock preview)" if job.is_mock else "AI-generated",
        "mock": bool(job.is_mock),
        "created_at": job.created_at.isoformat(),
        "error_code": job.error_code or None,
    }
    if job.status == job.STATUS_COMPLETED and job.storage_key:
        result["image_url"] = image_storage().url(job.storage_key)
    return result


def _paid_gate(paid_worker):
    """Re-evaluated before reserving and again just before the provider call."""
    return paid_worker_enabled() if paid_worker else paid_provider_enabled()


def process_next_image_job():
    """Run exactly one job. A claimed/uncertain job is NEVER auto-retried."""
    mock_worker = worker_enabled()
    paid_worker = not mock_worker and paid_worker_enabled()
    worker_mode = mock_worker or paid_worker
    if not (enabled() or worker_mode):
        return None
    with transaction.atomic():
        qs = AIImageJob.objects.filter(status=AIImageJob.STATUS_QUEUED).order_by("created_at")
        # A mock-only Worker MUST NOT claim paid provider jobs.
        if mock_worker:
            qs = qs.filter(provider="mock")
        elif paid_worker:
            # A paid Worker only claims paid jobs; it never processes mock work.
            qs = qs.filter(provider="openai")
        if connection.features.has_select_for_update_skip_locked:
            qs = qs.select_for_update(skip_locked=True)
        elif connection.features.has_select_for_update:
            qs = qs.select_for_update()
        job = qs.first()
        if job is None:
            return None
        if not actor_allowed(job.owner, worker=worker_mode):
            job.status = AIImageJob.STATUS_FAILED
            job.error_code = "authorization_revoked"
            job.prompt = ""
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error_code", "prompt", "finished_at", "updated_at"])
            return job.pk
        job.status = AIImageJob.STATUS_RUNNING
        job.attempts += 1
        job.save(update_fields=["status", "attempts", "updated_at"])
        job_id = job.pk
    reservation = None
    provider_called = False
    settlement_attempted = False
    safety_id = None
    try:
        # Storage must exist before any model/ledger work.
        image_storage()
        if job.provider == "openai":
            from apps.ai_ledger.service import (
                StagingDailyLimit, reserve_with_config, settle,
            )
            from .policy import image_ledger_config, max_request_micro, safety_identifier
            if (not _paid_gate(paid_worker) or not actor_allowed(job.owner, worker=worker_mode)
                    or job.model_id != getattr(
                        settings, "VORNEQ_AI_IMAGE_MODEL", "")):
                raise ImageQueueError("paid provider disabled")
            per_request_cap = max_request_micro()
            safety_id = safety_identifier(job.owner_id)
            if per_request_cap is None or safety_id is None:
                raise ImageQueueError("paid provider controls unavailable")
            daily = StagingDailyLimit(
                max_requests=_limit("VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS", 50),
                cap_micro=_limit("VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD", 2_000_000_000),
            )
            reservation = reserve_with_config(
                image_ledger_config(), environment="staging",
                service_id=os.environ.get("RENDER_SERVICE_ID", ""),
                git_sha=os.environ.get("RENDER_GIT_COMMIT", ""),
                actor_id=job.owner_id, model=job.model_id,
                input_bytes=len(job.prompt.encode("utf-8")),
                max_output_tokens=getattr(settings, "VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND", 0),
                staging_daily=daily,
            )
            # Store ledger reservation ID before the irreversible provider call.
            AIImageJob.objects.filter(pk=job_id, status=AIImageJob.STATUS_RUNNING).update(
                reservation_id=reservation.id
            )
            if reservation.amount_micro > per_request_cap:
                # Worst-case cost exceeds the per-request ceiling: provably not sent.
                raise ImageProviderError("request over cost ceiling",
                                         code="cost_ceiling_exceeded", request_sent=False)
            if not _paid_gate(paid_worker) or not actor_allowed(job.owner, worker=worker_mode):
                raise ImageProviderError("paid provider gate closed", code="paid_disabled",
                                         request_sent=False)
            provider = OpenAIImageProvider()
        else:
            provider = MockImageProvider()
        provider_called = True
        output = provider.generate(prompt=job.prompt, model=job.model_id, size=job.image_size,
                                   safety_identifier=safety_id)
        key, digest = store_image(job=job, content=output.content)
        if reservation is not None:
            usage = None
            if type(output.input_tokens) is int and type(output.output_tokens) is int:
                usage = (output.input_tokens, output.output_tokens)
            settlement_attempted = True
            ledger_state = settle(reservation, usage=usage, outcome="image_generated")
            bound = getattr(settings, "VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND", 0)
            over_bound = usage is not None and usage[1] > bound
            if ledger_state != "finalized" or over_bound:
                # No verified ledger commit (or usage beyond the reserved bound)
                # means no completed, downloadable image. Keep the private object
                # reference for manual reconciliation.
                AIImageJob.objects.filter(pk=job_id, status=AIImageJob.STATUS_RUNNING).update(
                    status=AIImageJob.STATUS_UNCERTAIN,
                    prompt="", storage_key=key, image_digest=digest,
                    is_mock=output.is_mock,
                    error_code=("usage_exceeded_bound" if ledger_state == "finalized"
                                else "ledger_settlement_unconfirmed"),
                    finished_at=timezone.now(),
                )
                return job_id
        AIImageJob.objects.filter(pk=job_id, status=AIImageJob.STATUS_RUNNING).update(
            status=AIImageJob.STATUS_COMPLETED,
            prompt="", storage_key=key,
            image_digest=digest,
            is_mock=output.is_mock, finished_at=timezone.now(),
        )
    except ImageProviderError as exc:
        _finish_after_provider_error(job_id, reservation, exc,
                                     settlement_attempted=settlement_attempted)
    except Exception as exc:
        # Provider may have billed before returning/raising. Never silently retry.
        from apps.ai_core.engine.budget import BudgetExceeded
        error_code = ("ledger_refused" if reservation is None and isinstance(exc, BudgetExceeded)
                      else "provider_or_storage_unavailable")
        if reservation is not None and not settlement_attempted:
            from apps.ai_ledger.service import settle
            try:
                settle(reservation, usage=None, outcome="image_uncertain")
            except Exception:
                # Never strand the image job just because a ledger error escaped.
                # The reserved allowance remains held for manual reconciliation.
                pass
        AIImageJob.objects.filter(pk=job_id, status=AIImageJob.STATUS_RUNNING).update(
            status=AIImageJob.STATUS_UNCERTAIN if reservation is not None and provider_called
                   else AIImageJob.STATUS_FAILED,
            prompt="", error_code=error_code,
            finished_at=timezone.now(),
        )
    return job_id


def _finish_after_provider_error(job_id, reservation, exc, *, settlement_attempted):
    """Release ONLY provably-unsent paid requests; everything else stays UNCERTAIN."""
    code = getattr(exc, "code", "provider_error") or "provider_error"
    status = AIImageJob.STATUS_FAILED
    if reservation is not None and not settlement_attempted:
        from apps.ai_ledger.service import RELEASED, release, settle
        if exc.request_sent is False:
            try:
                released = release(reservation, reason=code[:30])
            except Exception:
                released = None
            if released != RELEASED:
                status, code = AIImageJob.STATUS_UNCERTAIN, "ledger_release_unconfirmed"
        else:
            try:
                settle(reservation, usage=None, outcome=("uncertain:" + code)[:40])
            except Exception:
                pass
            status = AIImageJob.STATUS_UNCERTAIN
    elif reservation is not None:
        status = AIImageJob.STATUS_UNCERTAIN
    AIImageJob.objects.filter(pk=job_id, status=AIImageJob.STATUS_RUNNING).update(
        status=status, prompt="", error_code=code[:40], finished_at=timezone.now(),
    )
