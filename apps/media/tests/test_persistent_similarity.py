from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.media.embedding import DeterministicLocalEmbeddingProvider
from apps.media.models import MediaAsset, MediaEmbedding
from apps.media.similarity import MediaSimilarityService
from apps.media.vector_index import DatabaseVectorIndex, VectorRecord


class PersistentSimilarityTests(TestCase):
    def _image(self, *, payload=b"persistent-image", active=True):
        return MediaAsset.objects.create(
            media_type=MediaAsset.MediaType.IMAGE,
            title="Persistent image",
            file=SimpleUploadedFile("persistent.jpg", payload, content_type="image/jpeg"),
            mime_type="image/jpeg",
            byte_size=len(payload),
            width=100,
            height=100,
            is_active=active,
        )

    def setUp(self):
        self.provider = DeterministicLocalEmbeddingProvider()

    def test_database_index_persists_across_instances(self):
        asset = self._image()
        service = MediaSimilarityService(provider=self.provider, index=DatabaseVectorIndex())
        service.index_media_asset(asset)

        fresh_service = MediaSimilarityService(
            provider=self.provider,
            index=DatabaseVectorIndex(),
        )
        results = fresh_service.search_by_image(
            b"persistent-image",
            mime_type="image/jpeg",
        )

        self.assertEqual(MediaEmbedding.objects.count(), 1)
        self.assertEqual(results[0]["id"], str(asset.pk))
        self.assertAlmostEqual(results[0]["similarity_score"], 1.0, places=6)

    def test_database_index_keeps_embedding_policies_separate(self):
        asset = self._image()
        vector = self.provider.embed_image(b"persistent-image", mime_type="image/jpeg")
        index = DatabaseVectorIndex()
        index.upsert(VectorRecord(
            media_asset_id=str(asset.pk),
            vector=vector,
            embedding_policy="other-policy",
        ))

        results = index.search(
            vector,
            embedding_policy=self.provider.descriptor.policy,
        )
        self.assertEqual(results, [])

    def test_image_api_is_ephemeral_and_returns_discovery_note(self):
        asset = self._image()
        MediaSimilarityService(
            provider=self.provider,
            index=DatabaseVectorIndex(),
        ).index_media_asset(asset)
        before_count = MediaAsset.objects.count()

        response = self.client.post(
            reverse("media:search_image"),
            {
                "image": SimpleUploadedFile(
                    "query.jpg",
                    b"persistent-image",
                    content_type="image/jpeg",
                ),
                "limit": "5",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["results"][0]["id"], str(asset.pk))
        self.assertIn("discovery only", payload["note"])
        self.assertEqual(MediaAsset.objects.count(), before_count)
        self.assertNotIn("url", payload["results"][0])

    def test_text_api_searches_compatible_local_space(self):
        response = self.client.post(
            reverse("media:search_text"),
            data='{"text":"example","limit":5}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    @override_settings(DEBUG=False)
    def test_production_api_fails_closed_without_real_provider(self):
        response = self.client.post(
            reverse("media:search_text"),
            data='{"text":"example"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "embedding_provider_not_configured")
