"""Owner-only, marked PNGs in private persistent object storage."""
from __future__ import annotations

from io import BytesIO
import hashlib

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from PIL import Image, ImageDraw

from .providers import validate_png


def durable_storage_ready():
    config = getattr(settings, "STORAGES", {}).get("ai_images")
    if not isinstance(config, dict) or config.get("BACKEND") != "storages.backends.s3.S3Storage":
        return False
    options = config.get("OPTIONS", {})
    return bool(
        isinstance(options, dict)
        and options.get("bucket_name")
        and options.get("querystring_auth", True) is True
        and options.get("default_acl") in (None, "private")
        and not options.get("custom_domain")
        # R2 rejects legacy SigV2 presigned URLs; never report such a config as ready.
        and options.get("signature_version") == "s3v4"
    )


def image_storage():
    if "ai_images" not in getattr(settings, "STORAGES", {}):
        raise ValueError("image storage not configured")
    return storages["ai_images"]


def label_png(content: bytes, *, mock: bool = False) -> bytes:
    """Embed a visible, unambiguous AI label in every delivered PNG."""
    validate_png(content)
    with Image.open(BytesIO(content)) as image:
        canvas = image.convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")
    label = "AI MOCK" if mock else "AI GENERATED"
    if canvas.width < 160:
        label = "AI"
    box = draw.textbbox((0, 0), label)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    pad = max(3, min(12, canvas.width // 100))
    h = text_h + pad * 2
    w = text_w + pad * 2
    x, y = max(0, canvas.width - w), max(0, canvas.height - h)
    draw.rectangle((x, y, canvas.width, canvas.height), fill=(0, 0, 0, 190))
    draw.text((x + pad, y + pad - box[1]), label, fill=(255, 255, 255, 255))
    result = BytesIO()
    canvas.save(result, format="PNG")
    return validate_png(result.getvalue())


def store_image(*, job, content: bytes):
    labeled = label_png(content, mock=job.provider == "mock")
    key = "ai-generated/{}/{}.png".format(job.owner_id, job.pk.hex)
    storage = image_storage()
    name = storage.save(key, ContentFile(labeled, name=key))
    if name != key:
        storage.delete(name)
        raise ValueError("unexpected image storage path")
    return name, hashlib.sha256(labeled).hexdigest()


def image_url(key: str):
    return image_storage().url(key)
