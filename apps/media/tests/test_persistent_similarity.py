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

    # P0 MEDIA HOLD (OWNER-DEC-MEDIA-P0A-Z1-01): the similarity endpoints are
    # disabled independently of DEBUG. These two tests previously expected
    # HTTP 200 for an anonymous caller with DEBUG=True; that was the AI-03
    # authorization gap. They now assert the fail-closed hold instead.
    @override_settings(DEBUG=True)
    def test_image_api_is_held_even_with_debug_and_discloses_nothing(self):
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

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "embedding_provider_not_configured")
        self.assertNotIn(str(asset.pk), response.content.decode())
        self.assertNotIn(asset.title, response.content.decode())
        self.assertEqual(MediaAsset.objects.count(), before_count)

    @override_settings(DEBUG=True)
    def test_text_api_is_held_even_with_debug(self):
        response = self.client.post(
            reverse("media:search_text"),
            data='{"text":"example","limit":5}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "embedding_provider_not_configured")

    @override_settings(DEBUG=False)
    def test_production_api_fails_closed_without_real_provider(self):
        response = self.client.post(
            reverse("media:search_text"),
            data='{"text":"example"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "embedding_provider_not_configured")
