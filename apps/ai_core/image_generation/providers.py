"""Image providers. Mock is deterministic and never constructs a network client."""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from io import BytesIO
from PIL import Image
from django.conf import settings


class ImageProviderError(Exception):
    """Safe error, with no prompt, token, URL or provider response text."""


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
    def generate(self, *, prompt: str, model: str, size: str) -> ImageResult:
        # Explicit synthetic placeholder; does not pretend to be AI-generated art.
        canvas = Image.new("RGB", (64, 64), (230, 230, 230))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return ImageResult(validate_png(buffer.getvalue()), is_mock=True)


class OpenAIImageProvider:
    def generate(self, *, prompt: str, model: str, size: str) -> ImageResult:
        from .policy import MODELS, SIZES, paid_provider_enabled
        if (not paid_provider_enabled() or model not in MODELS or size not in SIZES
                or model != getattr(settings, "VORNEQ_AI_IMAGE_MODEL", "")):
            raise ImageProviderError("paid image generation disabled")
        # Import only after every runtime gate. The key stays in Render env.
        from openai import OpenAI
        import os
        try:
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=90.0, max_retries=0)
            check = client.moderations.create(model="omni-moderation-latest", input=prompt)
            if not check.results or check.results[0].flagged:
                raise ImageProviderError("content not allowed")
            response = client.images.generate(
                model=model, prompt=prompt, n=1, size=size,
                quality="low", output_format="png", moderation="auto",
            )
            if not response.data or not response.data[0].b64_json:
                raise ImageProviderError("missing image")
            data = validate_png(base64.b64decode(response.data[0].b64_json, validate=True))
            usage = getattr(response, "usage", None)
            i = getattr(usage, "input_tokens", None)
            o = getattr(usage, "output_tokens", None)
            return ImageResult(
                data, i if type(i) is int else None,
                o if type(o) is int else None, is_mock=False
            )
        except ImageProviderError:
            raise
        except (binascii.Error, ValueError) as exc:
            raise ImageProviderError("invalid provider image data") from exc
        except Exception as exc:
            # No exception text: provider errors can include sensitive context.
            raise ImageProviderError("provider outcome uncertain") from exc
