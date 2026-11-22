"""Read-only image history and same-origin original-PNG download.

Nothing here reserves ledger funds, constructs a provider client or signs a URL.
History is metadata-only; bytes leave only through the owner-scoped download view.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone as dt_timezone

from django.core import signing
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from apps.ai_core.models import AIImageJob
from .policy import actor_allowed
from .providers import ImageProviderError, validate_png
from .storage import image_storage

_logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_CURSOR_LENGTH = 512
CURSOR_MAX_AGE_SECONDS = 24 * 60 * 60
CURSOR_SALT = "vorneq.ai.image.history.cursor.v1"
# Same ceiling validate_png enforces; checked before and while reading.
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
READ_DEADLINE_SECONDS = 20.0


def _respond(data, code=200):
    response = JsonResponse(data, status=code)
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _gate(request):
    """Same contracts as the existing job endpoints: 401, then 404."""
    if not request.user.is_authenticated:
        return _respond({"error": "authentication_required"}, 401)
    if not actor_allowed(request.user):
        return _respond({"error": "unavailable"}, 404)
    return None


def history_item(job):
    """Metadata only: no prompt, digest, storage key, reservation or URL."""
    return {
        "id": str(job.pk),
        "status": job.status,
        "model": job.model_id,
        "size": job.image_size,
        "created_at": job.created_at.isoformat(),
        "mock": bool(job.is_mock),
    }


def encode_cursor(user, job):
    return signing.dumps(
        {"u": str(user.pk), "t": job.created_at.isoformat(), "p": str(job.pk)},
        salt=CURSOR_SALT, compress=True,
    )


class InvalidCursor(Exception):
    pass


def decode_cursor(user, token):
    """Return (aware timestamp, UUID) or raise InvalidCursor; never guesses."""
    if not isinstance(token, str) or not 1 <= len(token) <= MAX_CURSOR_LENGTH:
        raise InvalidCursor()
    try:
        data = signing.loads(token, salt=CURSOR_SALT, max_age=CURSOR_MAX_AGE_SECONDS)
    except signing.BadSignature:  # includes SignatureExpired
        raise InvalidCursor() from None
    if not isinstance(data, dict) or set(data) != {"u", "t", "p"}:
        raise InvalidCursor()
    if not all(isinstance(data[key], str) for key in data):
        raise InvalidCursor()
    if data["u"] != str(user.pk):
        raise InvalidCursor()
    try:
        stamp = datetime.fromisoformat(data["t"])
        job_id = uuid.UUID(data["p"])
    except (ValueError, TypeError):
        raise InvalidCursor() from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise InvalidCursor()
    return stamp.astimezone(dt_timezone.utc), job_id


def _page_size(raw):
    if raw is None:
        return DEFAULT_PAGE_SIZE
    if not raw.isascii() or not raw.isdigit() or len(raw) > 3:
        return None
    value = int(raw)
    return value if 1 <= value <= MAX_PAGE_SIZE else None


@require_GET
def image_history_view(request):
    denied = _gate(request)
    if denied:
        return denied
    size = _page_size(request.GET.get("limit"))
    if size is None:
        return _respond({"error": "invalid_request"}, 400)
    queryset = AIImageJob.objects.filter(
        owner=request.user, status=AIImageJob.STATUS_COMPLETED,
    ).exclude(storage_key="")
    token = request.GET.get("cursor")
    if token is not None:
        try:
            stamp, job_id = decode_cursor(request.user, token)
        except InvalidCursor:
            # Never fall back to page one: the client must know the cursor failed.
            return _respond({"error": "invalid_cursor"}, 400)
        queryset = queryset.filter(Q(created_at__lt=stamp) | Q(created_at=stamp, pk__lt=job_id))
    rows = list(queryset.order_by("-created_at", "-pk")[:size + 1])
    page, more = rows[:size], len(rows) > size
    return _respond({
        "results": [history_item(job) for job in page],
        "next_cursor": encode_cursor(request.user, page[-1]) if more else None,
        "has_more": more,
    })


class _DownloadError(Exception):
    pass


def _read_bounded(storage, key):
    """Read the whole object under hard size and time limits; always close it."""
    try:
        declared = storage.size(key)
    except Exception as exc:  # storage backends raise heterogeneous errors
        raise _DownloadError("storage_unavailable") from exc
    if type(declared) is not int or not 1 <= declared <= MAX_DOWNLOAD_BYTES:
        raise _DownloadError("storage_invalid")
    deadline = time.monotonic() + READ_DEADLINE_SECONDS
    chunks, total = [], 0
    try:
        handle = storage.open(key, "rb")
    except Exception as exc:
        raise _DownloadError("storage_unavailable") from exc
    try:
        while True:
            chunk = handle.read(min(READ_CHUNK_BYTES, MAX_DOWNLOAD_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise _DownloadError("storage_invalid")
            if time.monotonic() > deadline:
                raise _DownloadError("storage_timeout")
            chunks.append(chunk)
    except _DownloadError:
        raise
    except Exception as exc:
        raise _DownloadError("storage_unavailable") from exc
    finally:
        try:
            handle.close()
        except Exception:  # never mask the primary outcome
            _logger.warning("image storage handle close failed")
    if total != declared:
        raise _DownloadError("storage_invalid")
    return b"".join(chunks)


@require_GET
def image_download_view(request, job_id):
    denied = _gate(request)
    if denied:
        return denied
    job = AIImageJob.objects.filter(
        pk=job_id, owner=request.user, status=AIImageJob.STATUS_COMPLETED,
    ).first()
    if job is None or not job.storage_key:
        return _respond({"error": "not_found"}, 404)
    # The key is derived, never trusted from the row alone.
    expected = "ai-generated/{}/{}.png".format(job.owner_id, job.pk.hex)
    if job.storage_key != expected:
        return _respond({"error": "not_found"}, 404)
    try:
        data = _read_bounded(image_storage(), expected)
        # The validator needs every byte, so it runs before any response byte exists.
        validate_png(data)
    except _DownloadError as exc:
        _logger.warning("image download failed: %s", exc)
        return _respond({"error": "storage_unavailable"}, 502)
    except (ImageProviderError, ValueError):
        _logger.warning("image download rejected: invalid stored image")
        return _respond({"error": "storage_unavailable"}, 502)
    except Exception:
        _logger.warning("image download failed: storage configuration")
        return _respond({"error": "storage_unavailable"}, 502)
    if job.image_digest and hashlib.sha256(data).hexdigest() != job.image_digest:
        _logger.warning("image download rejected: digest mismatch")
        return _respond({"error": "storage_unavailable"}, 502)
    response = HttpResponse(data, content_type="image/png")
    response["Content-Disposition"] = 'attachment; filename="VORNEQ-image-{}.png"'.format(job.pk)
    response["Content-Length"] = str(len(data))
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
