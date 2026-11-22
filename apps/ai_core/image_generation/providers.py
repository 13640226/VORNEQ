"""Image providers. Mock is deterministic and never constructs a network client."""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from io import BytesIO
from PIL import Image
from django.conf import settings


class ImageProviderError(Exception):
    """Safe error, with no prompt, token, URL or provider response text.

    ``code`` is a short, fixed classification for audit and user messages.
    ``request_sent`` is False ONLY when the paid image request provably never
    left this process (gate, configuration, SDK construction, pre-moderation).
    Every other case (None or True) must be treated as possibly billed.
    """

    def __init__(self, message="provider error", *, code="provider_error", request_sent=None):
        super().__init__(message)
        self.code = code
        self.request_sent = request_sent


@dataclass(frozen=True)
class ImageResult:
    content: bytes
    input_tokens: int | None = None
    output_tokens: int | None = None
    is_mock: bool = False


# Mock pixels are generated in-memory; no API access, no fake provider output.


def validate_png(data: bytes) -> bytes:
    if not isinstance(data, bytes) or not 1 <= len(data) <= 12 * 1024 * 1024:
        raise ImageProviderError("invalid image size")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG" or image.width * image.height > 12_000_000:
                raise ImageProviderError("invalid image format")
            image.verify()
    except (OSError, ValueError, SyntaxError) as exc:
        raise ImageProviderError("invalid image data") from exc
    return data


class MockImageProvider:
    def generate(self, *, prompt: str, model: str, size: str,
                 safety_identifier: str | None = None) -> ImageResult:
        # Explicit synthetic placeholder; does not pretend to be AI-generated art.
        canvas = Image.new("RGB", (64, 64), (230, 230, 230))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return ImageResult(validate_png(buffer.getvalue()), is_mock=True)


COMPLEXITIES = frozenset({"low", "medium", "high"})
QUALITY = "low"
OUTPUT_FORMAT = "png"
_SAFETY_ID = re.compile(r"vq_[0-9a-f]{64}\Z")


def configured_complexity():
    value = getattr(settings, "VORNEQ_AI_IMAGE_COMPLEXITY", "low")
    return value if isinstance(value, str) and value in COMPLEXITIES else None


def classify_provider_exception(exc):
    """Map an SDK/transport exception to a fixed code. Never uses its text."""
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    status = status if type(status) is int else None
    if "Timeout" in name or isinstance(exc, TimeoutError):
        return "provider_timeout"
    if "Connection" in name or isinstance(exc, ConnectionError):
        return "provider_connection"
    if status == 400:
        code = getattr(exc, "code", None)
        body = getattr(exc, "body", None)
        if code == "moderation_blocked" or (
                isinstance(body, dict) and body.get("code") == "moderation_blocked"):
            return "provider_moderation_blocked"
        return "provider_bad_request"
    if status == 401:
        return "provider_auth"
    if status == 403:
        return "provider_permission"
    if status == 429:
        return "provider_rate_limited"
    if status is not None and status >= 500:
        return "provider_server_error"
    if status is not None:
        return "provider_status_error"
    return "provider_outcome_uncertain"


class OpenAIImageProvider:
    """Paid OpenAI Images API call. Exactly one attempt, never retried.

    HTTP 400/401/429/5xx, timeouts and disconnects AFTER the request was sent
    are classified but remain request_sent=True: without proof that nothing was
    billed, the ledger keeps them UNCERTAIN.
    """

    def generate(self, *, prompt: str, model: str, size: str,
                 safety_identifier: str | None = None) -> ImageResult:
        from .policy import MODELS, SIZES, paid_provider_enabled, paid_worker_enabled
        # Both routes independently verify their own runtime identity and grant.
        # A worker must never need (or inherit) the web service identity.
        if (not (paid_provider_enabled() or paid_worker_enabled()) or model not in MODELS or size not in SIZES
                or model != getattr(settings, "VORNEQ_AI_IMAGE_MODEL", "")):
            raise ImageProviderError("paid image generation disabled",
                                     code="paid_disabled", request_sent=False)
        complexity = configured_complexity()
        if complexity is None:
            raise ImageProviderError("invalid complexity", code="invalid_configuration",
                                     request_sent=False)
        if not isinstance(safety_identifier, str) or not _SAFETY_ID.fullmatch(safety_identifier):
            raise ImageProviderError("safety identifier unavailable",
                                     code="safety_identifier_unavailable", request_sent=False)
        import os
        image_api_key = os.environ.get("VORNEQ_OPENAI_IMAGE_API_KEY", "")
        if not image_api_key.strip():
            raise ImageProviderError("dedicated image API key missing",
                                     code="image_api_key_missing", request_sent=False)
        try:
            # Import only after every runtime gate. The key stays in Render env.
            from openai import OpenAI
            # No fallback to OPENAI_API_KEY: image and chat projects are separate.
            client = OpenAI(api_key=image_api_key, timeout=90.0, max_retries=0)
        except Exception as exc:
            raise ImageProviderError("provider client unavailable", code="sdk_unavailable",
                                     request_sent=False) from exc
        try:
            check = client.moderations.create(model="omni-moderation-latest", input=prompt)
            flagged = not check.results or bool(check.results[0].flagged)
        except Exception as exc:
            # Moderation is a separate endpoint; the paid image request was not sent.
            raise ImageProviderError("moderation unavailable", code="moderation_unavailable",
                                     request_sent=False) from exc
        if flagged:
            raise ImageProviderError("content not allowed", code="prompt_moderated",
                                     request_sent=False)
        try:
            response = client.images.generate(
                model=model, prompt=prompt, n=1, size=size,
                quality=QUALITY, output_format=OUTPUT_FORMAT, moderation="auto",
                complexity=complexity, safety_identifier=safety_identifier,
            )
        except Exception as exc:
            # No exception text: provider errors can include sensitive context.
            raise ImageProviderError("provider outcome uncertain",
                                     code=classify_provider_exception(exc),
                                     request_sent=True) from exc
        try:
            if not response.data or not response.data[0].b64_json:
                raise ImageProviderError("missing image", code="provider_empty_response",
                                         request_sent=True)
            data = validate_png(base64.b64decode(response.data[0].b64_json, validate=True))
        except ImageProviderError as exc:
            if exc.request_sent is None:
                exc.code, exc.request_sent = "provider_invalid_image", True
            raise
        except (binascii.Error, ValueError, TypeError, AttributeError, IndexError) as exc:
            raise ImageProviderError("invalid provider image data",
                                     code="provider_invalid_image", request_sent=True) from exc
        usage = getattr(response, "usage", None)
        i = getattr(usage, "input_tokens", None)
        o = getattr(usage, "output_tokens", None)
        return ImageResult(
            data, i if type(i) is int and i >= 0 else None,
            o if type(o) is int and o >= 0 else None, is_mock=False
        )
