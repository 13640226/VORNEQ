from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.media.embedding import DeterministicLocalEmbeddingProvider
from apps.media.models import MediaAsset
from apps.media.similarity import MediaSimilarityService
from apps.media.vector_index import InMemoryVectorIndex, VectorRecord


class SimilarityFoundationTests(TestCase):
    def _image(self, *, title="Image", payload=b"image-data", active=True):
        return MediaAsset.objects.create(
            media_type=MediaAsset.MediaType.IMAGE,
            title=title,
            file=SimpleUploadedFile("image.jpg", payload, content_type="image/jpeg"),
            mime_type="image/jpeg",
            byte_size=len(payload),
            width=100,
            height=100,
            is_active=active,
        )

    def setUp(self):
        self.provider = DeterministicLocalEmbeddingProvider(dimensions=8)
        self.index = InMemoryVectorIndex()
        self.events = []
        self.service = MediaSimilarityService(
            provider=self.provider,
            index=self.index,
            telemetry_sink=self.events.append,
        )

    def test_index_and_search_same_image(self):
        asset = self._image(payload=b"same-image")
        self.service.index_media_asset(asset)

        results = self.service.search_by_image(
            b"same-image",
            mime_type="image/jpeg",
            limit=5,
        )

        self.assertEqual(results[0]["id"], str(asset.pk))
        self.assertAlmostEqual(results[0]["similarity_score"], 1.0, places=6)
        self.assertEqual(results[0]["embedding_policy"], self.provider.descriptor.policy)

    def test_inactive_media_is_not_returned(self):
        asset = self._image(payload=b"same-image")
        self.service.index_media_asset(asset)
        asset.is_active = False
        asset.save(update_fields=["is_active"])

        results = self.service.search_by_image(
            b"same-image",
            mime_type="image/jpeg",
        )

        self.assertEqual(results, [])

    def test_index_does_not_mix_embedding_policies(self):
        vector = self.provider.embed_image(b"same-image", mime_type="image/jpeg")
        self.index.upsert(
            VectorRecord(
                media_asset_id="other",
                vector=vector,
                embedding_policy="different-policy",
            )
        )

        results = self.index.search(
            vector,
            embedding_policy=self.provider.descriptor.policy,
        )

        self.assertEqual(results, [])

    def test_text_search_requires_provider_capability(self):
        provider = DeterministicLocalEmbeddingProvider(dimensions=8, supports_text=False)
        service = MediaSimilarityService(provider=provider, index=self.index)

        with self.assertRaises(NotImplementedError):
            service.search_by_text("example")

    def test_reindex_active_images_rebuilds_current_policy(self):
        first = self._image(title="First", payload=b"first")
        second = self._image(title="Second", payload=b"second")
        self._image(title="Inactive", payload=b"inactive", active=False)

        count = self.service.reindex_active_images()

        self.assertEqual(count, 2)
        first_results = self.service.search_by_image(b"first", mime_type="image/jpeg")
        second_results = self.service.search_by_image(b"second", mime_type="image/jpeg")
        self.assertEqual(first_results[0]["id"], str(first.pk))
        self.assertEqual(second_results[0]["id"], str(second.pk))

    def test_telemetry_records_operational_metadata(self):
        asset = self._image(payload=b"telemetry")
        self.service.index_media_asset(asset)
        self.service.search_by_image(b"telemetry", mime_type="image/jpeg")

        self.assertEqual([event.operation for event in self.events], ["index", "search_image"])
        self.assertTrue(all(event.provider == "local" for event in self.events))
        self.assertTrue(all(event.embedding_policy == self.provider.descriptor.policy for event in self.events))
        self.assertTrue(all(event.estimated_cost is None for event in self.events))

    def test_local_provider_is_deterministic(self):
        first = self.provider.embed_image(b"payload", mime_type="image/jpeg")
        second = self.provider.embed_image(b"payload", mime_type="image/jpeg")
        self.assertEqual(first, second)
