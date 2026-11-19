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
from .policy import SIZES, actor_allowed, enabled, paid_provider_enabled
from .providers import MockImageProvider, OpenAIImageProvider
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


def process_next_image_job():
    """Run exactly one job. A claimed/uncertain job is NEVER auto-retried."""
    if not enabled():
        return None
    with transaction.atomic():
        qs = AIImageJob.objects.filter(status=AIImageJob.STATUS_QUEUED).order_by("created_at")
        if connection.features.has_select_for_update_skip_locked:
            qs = qs.select_for_update(skip_locked=True)
        elif connection.features.has_select_for_update:
            qs = qs.select_for_update()
        job = qs.first()
        if job is None:
            return None
        if not actor_allowed(job.owner):
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
    try:
        # Storage must exist before any model/ledger work.
        image_storage()
        if job.provider == "openai":
            from apps.ai_ledger.service import (
                StagingDailyLimit, reserve_with_config, settle,
            )
            from .policy import image_ledger_config
            if (not paid_provider_enabled() or not actor_allowed(job.owner)
                    or job.model_id != getattr(
                        settings, "VORNEQ_AI_IMAGE_MODEL", "")):
                raise ImageQueueError("paid provider disabled")
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
            if not paid_provider_enabled() or not actor_allowed(job.owner):
                raise ImageQueueError("paid provider gate closed")
            provider = OpenAIImageProvider()
        else:
            provider = MockImageProvider()
        provider_called = True
        output = provider.generate(prompt=job.prompt, model=job.model_id, size=job.image_size)
        key, digest = store_image(job=job, content=output.content)
        if reservation is not None:
            usage = None
            if type(output.input_tokens) is int and type(output.output_tokens) is int:
                usage = (output.input_tokens, output.output_tokens)
            settlement_attempted = True
            ledger_state = settle(reservation, usage=usage, outcome="image_generated")
            if ledger_state != "finalized":
                # No verified ledger commit means no completed, downloadable image.
                # Keep the private object reference for manual reconciliation.
                AIImageJob.objects.filter(pk=job_id, status=AIImageJob.STATUS_RUNNING).update(
                    status=AIImageJob.STATUS_UNCERTAIN,
                    prompt="", storage_key=key, image_digest=digest,
                    is_mock=output.is_mock, error_code="ledger_settlement_unconfirmed",
                    finished_at=timezone.now(),
                )
                return job_id
        AIImageJob.objects.filter(pk=job_id, status=AIImageJob.STATUS_RUNNING).update(
            status=AIImageJob.STATUS_COMPLETED,
            prompt="", storage_key=key,
            image_digest=digest,
            is_mock=output.is_mock, finished_at=timezone.now(),
        )
    except Exception:
        # Provider may have billed before returning/raising. Never silently retry.
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
            prompt="", error_code="provider_or_storage_unavailable",
            finished_at=timezone.now(),
        )
    return job_id
