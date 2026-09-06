from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from apps.media.embedding import BaseEmbeddingProvider
from apps.media.models import MediaAsset
from apps.media.vector_index import BaseVectorIndex, VectorRecord


@dataclass(frozen=True)
class SimilarityTelemetryEvent:
    operation: str
    provider: str
    model: str
    model_version: str
    embedding_policy: str
    latency_ms: float
    input_size: int | None
    result_count: int | None
    estimated_cost: float | None
    status: str


TelemetrySink = Callable[[SimilarityTelemetryEvent], None]


def _noop_telemetry(_: SimilarityTelemetryEvent) -> None:
    return None


class MediaSimilarityService:
    """Discovery-only similarity service over active image MediaAssets."""

    def __init__(
        self,
        *,
        provider: BaseEmbeddingProvider,
        index: BaseVectorIndex,
        telemetry_sink: TelemetrySink | None = None,
    ):
        self.provider = provider
        self.index = index
        self.telemetry_sink = telemetry_sink or _noop_telemetry

    def _emit(
        self,
        *,
        operation: str,
        started_at: float,
        input_size: int | None,
        result_count: int | None,
        status: str,
    ) -> None:
        descriptor = self.provider.descriptor
        self.telemetry_sink(
            SimilarityTelemetryEvent(
                operation=operation,
                provider=descriptor.provider,
                model=descriptor.model,
                model_version=descriptor.version,
                embedding_policy=descriptor.policy,
                latency_ms=(perf_counter() - started_at) * 1000,
                input_size=input_size,
                result_count=result_count,
                estimated_cost=None,
                status=status,
            )
        )

    def index_media_asset(self, media_asset: MediaAsset) -> None:
        if media_asset.pk is None:
            raise ValueError("MediaAsset must be saved before indexing.")
        if not media_asset.is_active:
            self.index.remove(str(media_asset.pk))
            return
        if media_asset.media_type != MediaAsset.MediaType.IMAGE:
            raise ValueError("Visual similarity indexing currently supports image MediaAssets only.")

        started_at = perf_counter()
        try:
            with media_asset.file.open("rb") as file_handle:
                data = file_handle.read()
            vector = self.provider.embed_image(data, mime_type=media_asset.mime_type)
            self.index.upsert(
                VectorRecord(
                    media_asset_id=str(media_asset.pk),
                    vector=vector,
                    embedding_policy=self.provider.descriptor.policy,
                )
            )
        except Exception:
            self._emit(
                operation="index",
                started_at=started_at,
                input_size=None,
                result_count=None,
                status="failed",
            )
            raise
        self._emit(
            operation="index",
            started_at=started_at,
            input_size=media_asset.byte_size,
            result_count=None,
            status="success",
        )

    def reindex_active_images(self) -> int:
        policy = self.provider.descriptor.policy
        self.index.clear(embedding_policy=policy)
        count = 0
        queryset = MediaAsset.objects.filter(
            is_active=True,
            media_type=MediaAsset.MediaType.IMAGE,
        ).order_by("pk")
        for media_asset in queryset.iterator():
            self.index_media_asset(media_asset)
            count += 1
        return count

    def remove_media_asset(self, media_asset: MediaAsset) -> None:
        if media_asset.pk is not None:
            self.index.remove(str(media_asset.pk))

    def search_by_image(
        self,
        image_data: bytes,
        *,
        mime_type: str,
        limit: int = 10,
    ) -> list[dict]:
        started_at = perf_counter()
        try:
            query_vector = self.provider.embed_image(image_data, mime_type=mime_type)
            raw_results = self.index.search(
                query_vector,
                embedding_policy=self.provider.descriptor.policy,
                limit=limit,
            )
            results = self._resolve_results(raw_results)
        except Exception:
            self._emit(
                operation="search_image",
                started_at=started_at,
                input_size=len(image_data),
                result_count=None,
                status="failed",
            )
            raise
        self._emit(
            operation="search_image",
            started_at=started_at,
            input_size=len(image_data),
            result_count=len(results),
            status="success",
        )
        return results

    def search_by_text(self, text: str, *, limit: int = 10) -> list[dict]:
        if not self.provider.descriptor.supports_text:
            raise NotImplementedError("Configured provider does not support compatible text embeddings.")
        started_at = perf_counter()
        try:
            query_vector = self.provider.embed_text(text)
            raw_results = self.index.search(
                query_vector,
                embedding_policy=self.provider.descriptor.policy,
                limit=limit,
            )
            results = self._resolve_results(raw_results)
        except Exception:
            self._emit(
                operation="search_text",
                started_at=started_at,
                input_size=len(text.encode("utf-8")),
                result_count=None,
                status="failed",
            )
            raise
        self._emit(
            operation="search_text",
            started_at=started_at,
            input_size=len(text.encode("utf-8")),
            result_count=len(results),
            status="success",
        )
        return results

    def _resolve_results(self, raw_results: list[tuple[str, float]]) -> list[dict]:
        ids = [media_id for media_id, _ in raw_results]
        assets_by_pk = MediaAsset.objects.filter(pk__in=ids, is_active=True).in_bulk()
        assets = {str(pk): asset for pk, asset in assets_by_pk.items()}
        formatted = []
        for media_id, score in raw_results:
            asset = assets.get(media_id)
            if asset is None:
                continue
            formatted.append(
                {
                    "id": str(asset.pk),
                    "title": asset.title,
                    "media_type": asset.media_type,
                    "similarity_score": score,
                    "embedding_policy": self.provider.descriptor.policy,
                }
            )
        return formatted
