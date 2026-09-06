from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import math
from typing import Iterable


Vector = tuple[float, ...]


@dataclass(frozen=True)
class EmbeddingDescriptor:
    provider: str
    model: str
    version: str
    dimensions: int
    policy: str
    supports_image: bool = True
    supports_text: bool = False


class BaseEmbeddingProvider(ABC):
    """Provider-neutral embedding contract for discovery-only similarity."""

    @property
    @abstractmethod
    def descriptor(self) -> EmbeddingDescriptor:
        raise NotImplementedError

    @abstractmethod
    def embed_image(self, data: bytes, *, mime_type: str) -> Vector:
        raise NotImplementedError

    def embed_text(self, text: str) -> Vector:
        raise NotImplementedError("This embedding provider does not support text queries.")


def _normalize(values: Iterable[float]) -> Vector:
    vector = tuple(float(value) for value in values)
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return tuple(value / norm for value in vector)


class DeterministicLocalEmbeddingProvider(BaseEmbeddingProvider):
    """Dependency-free deterministic adapter for development and tests.

    This adapter is not a semantic production model. It exists to exercise the
    provider/index contracts without adding an external SDK or model dependency.
    """

    def __init__(self, *, dimensions: int = 16, supports_text: bool = True):
        if dimensions < 2:
            raise ValueError("Embedding dimensions must be at least 2.")
        self._dimensions = dimensions
        self._supports_text = supports_text

    @property
    def descriptor(self) -> EmbeddingDescriptor:
        return EmbeddingDescriptor(
            provider="local",
            model="deterministic-hash",
            version="1",
            dimensions=self._dimensions,
            policy=f"deterministic-hash-v1-d{self._dimensions}",
            supports_text=self._supports_text,
        )

    def _embed(self, payload: bytes) -> Vector:
        values = []
        seed = payload
        counter = 0
        while len(values) < self._dimensions:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            for byte in digest:
                values.append((byte / 127.5) - 1.0)
                if len(values) == self._dimensions:
                    break
            counter += 1
        return _normalize(values)

    def embed_image(self, data: bytes, *, mime_type: str) -> Vector:
        if not data:
            raise ValueError("Image query data must not be empty.")
        if not mime_type.startswith("image/"):
            raise ValueError("Image embedding requires an image MIME type.")
        return self._embed(b"image\0" + mime_type.encode("utf-8") + b"\0" + data)

    def embed_text(self, text: str) -> Vector:
        if not self._supports_text:
            return super().embed_text(text)
        normalized = text.strip()
        if not normalized:
            raise ValueError("Text query must not be empty.")
        return self._embed(b"text\0" + normalized.encode("utf-8"))
