from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math

from apps.media.embedding import Vector


@dataclass(frozen=True)
class VectorRecord:
    media_asset_id: str
    vector: Vector
    embedding_policy: str


class BaseVectorIndex(ABC):
    """Backend-neutral index contract for derived similarity infrastructure."""

    @abstractmethod
    def upsert(self, record: VectorRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove(self, media_asset_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_vector: Vector,
        *,
        embedding_policy: str,
        limit: int = 10,
    ) -> list[tuple[str, float]]:
        raise NotImplementedError

    @abstractmethod
    def clear(self, *, embedding_policy: str | None = None) -> None:
        raise NotImplementedError


def _cosine_similarity(left: Vector, right: Vector) -> float:
    if len(left) != len(right):
        raise ValueError("Cannot compare vectors with different dimensions.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    return dot / (left_norm * right_norm)


class InMemoryVectorIndex(BaseVectorIndex):
    """Process-local adapter for tests and development only."""

    def __init__(self):
        self._records: dict[tuple[str, str], VectorRecord] = {}

    def upsert(self, record: VectorRecord) -> None:
        key = (record.embedding_policy, record.media_asset_id)
        self._records[key] = record

    def remove(self, media_asset_id: str) -> None:
        keys = [key for key in self._records if key[1] == media_asset_id]
        for key in keys:
            self._records.pop(key, None)

    def search(
        self,
        query_vector: Vector,
        *,
        embedding_policy: str,
        limit: int = 10,
    ) -> list[tuple[str, float]]:
        if limit < 1:
            raise ValueError("Search limit must be at least 1.")
        results = []
        for (policy, media_asset_id), record in self._records.items():
            if policy != embedding_policy:
                continue
            score = _cosine_similarity(query_vector, record.vector)
            results.append((media_asset_id, score))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:limit]

    def clear(self, *, embedding_policy: str | None = None) -> None:
        if embedding_policy is None:
            self._records.clear()
            return
        keys = [key for key in self._records if key[0] == embedding_policy]
        for key in keys:
            self._records.pop(key, None)
