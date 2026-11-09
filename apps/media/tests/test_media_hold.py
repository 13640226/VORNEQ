"""P0 Media Security Hold regression tests (OWNER-DEC-MEDIA-P0A-Z1-01).

Policy: OWNER-DEC-MEDIA-POLICY-01 (DEFAULT_PRIVATE, PUBLIC_MEDIA_SEARCH =
TEMPORARILY_DISABLED). All data is synthetic. No provider or network access.
Checklist IDs refer to VORNEQ_AI_MEDIA_P0A_VERIFIED_REVIEW_AND_IMPLEMENTATION_PLAN_V1 §8.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.content.models import Article, Category
from apps.media import api as media_api
from apps.media.models import MediaAsset
from apps.search.services import MediaAssetAdapter, UnifiedSearch
from library.models import LibraryItem
from marketplace.models import Product

User = get_user_model()

MEDIA_TITLE = "Synthhold private media title"
MEDIA_ALT = "Synthhold private alt text"
SEARCH_TERM = "synthhold"


class _HoldFixture(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="synthhold-user", password="x-Synth-1!")
        self.staff = User.objects.create_user(
            username="synthhold-staff", password="x-Synth-1!", is_staff=True
        )
        category = Category.objects.create(name="Synthhold Category")
        Article.objects.create(
            title="Synthhold Article",
            summary="Synthhold summary",
            content="Synthhold content",
            category=category,
            is_published=True,
        )
        Product.objects.create(
            seller=self.user,
            title="Synthhold Product",
            short_description="Synthhold product",
            status=Product.STATUS_APPROVED,
            is_published=True,
            price="10.00",
        )
        LibraryItem.objects.create(
            title="Synthhold Book",
            slug="synthhold-book",
            short_description="Synthhold library",
            author="Synthhold Author",
            item_type="book",
            is_published=True,
        )
        self.non_media_total = 3
        self.asset = MediaAsset.objects.create(
            title=MEDIA_TITLE,
            alt_text=MEDIA_ALT,
            media_type=MediaAsset.MediaType.IMAGE,
            file=SimpleUploadedFile("synthhold.png", b"synthhold-bytes", content_type="image/png"),
            mime_type="image/png",
            byte_size=15,
            width=10,
            height=10,
            is_active=True,
        )

    def assertNoMediaDisclosure(self, response_or_text):
        body = (
            response_or_text
            if isinstance(response_or_text, str)
            else response_or_text.content.decode("utf-8", "replace")
        )
        self.assertNotIn(MEDIA_TITLE, body)
        self.assertNotIn(MEDIA_ALT, body)
        self.assertNotIn(str(self.asset.pk), body)
        self.assertNotIn(self.asset.file.name, body)  # H09: no storage path / URL
        self.assertNotIn("media:", body.replace("media:search", ""))


@override_settings(DEBUG=False)
class PublicSearchHoldTests(_HoldFixture):
    def test_h01_api_search_unfiltered_keeps_non_media_results(self):
        response = Client().get("/api/search/", {"q": SEARCH_TERM})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], self.non_media_total)
        self.assertEqual(
            {r["key"].split(":", 1)[0] for r in data["results"]},
            {"article", "product", "library"},
        )
        self.assertNoMediaDisclosure(response)

    def test_h02_api_search_type_mediaasset_is_empty(self):
        response = Client().get("/api/search/", {"type": "mediaasset"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.assertEqual(response.json()["total"], 0)
        self.assertNoMediaDisclosure(response)

    def test_h03_api_search_media_type_filter_returns_no_media(self):
        response = Client().get("/api/search/", {"media_type": "image"})
        self.assertEqual(response.status_code, 200)
        self.assertNoMediaDisclosure(response)

    def test_h04_html_surfaces_return_200_without_media(self):
        client = Client()
        for language in ("fa", "en", "de"):
            for path, params in (
                (f"/{language}/discover/", {}),
                (f"/{language}/discover/", {"q": SEARCH_TERM}),
                (f"/{language}/discover/", {"type": "mediaasset"}),
                (f"/{language}/discover/media/", {}),
                (f"/{language}/search/", {"q": SEARCH_TERM}),
                (f"/{language}/search/", {"type": "mediaasset"}),
            ):
                with self.subTest(path=path, params=params):
                    response = client.get(path, params)
                    self.assertEqual(response.status_code, 200)
                    self.assertNoMediaDisclosure(response)

    def test_h05_bounded_and_narrow_paths_exclude_media_without_errors(self):
        service = UnifiedSearch()
        for page in (0, 1, 2):
            with self.subTest(page=page):
                payload = service.search(SEARCH_TERM, page=page, page_size=2, language="en")
                self.assertNoMediaDisclosure(repr(payload))
        unfiltered = service.search("", page=1, language="en")
        self.assertNoMediaDisclosure(repr(unfiltered))

    def test_h06_counts_and_pagination_exclude_media(self):
        payload = UnifiedSearch().search(SEARCH_TERM, page=1, page_size=2, language="en")
        self.assertEqual(payload["total"], self.non_media_total)
        self.assertEqual(payload["total_pages"], 2)
        self.assertTrue(payload["has_next"])
        page_two = UnifiedSearch().search(SEARCH_TERM, page=2, page_size=2, language="en")
        self.assertEqual(len(page_two["results"]), 1)
        self.assertFalse(page_two["has_next"])

    def test_default_registration_excludes_media_adapter(self):
        self.assertFalse(
            any(isinstance(a, MediaAssetAdapter) for a in UnifiedSearch().adapters)
        )

    def test_h09_media_adapter_never_serializes_storage_url(self):
        result = MediaAssetAdapter().serialize(self.asset, language="en")
        self.assertIsNone(result.image_url)

    def test_h12_templates_offer_no_media_filters(self):
        client = Client()
        for path in ("/en/search/", "/en/discover/"):
            with self.subTest(path=path):
                body = client.get(path).content.decode()
                self.assertNotIn('value="mediaasset"', body)
                self.assertNotIn("?type=mediaasset", body)
                self.assertNotIn('name="media_type"', body)
                self.assertNotIn("media_type=", body)


class MediaSimilarityApiHoldTests(_HoldFixture):
    def _post_image(self, client, *, csrf_header=True):
        headers = {}
        if csrf_header and "csrftoken" in client.cookies:
            headers["HTTP_X_CSRFTOKEN"] = client.cookies["csrftoken"].value
        return client.post(
            reverse("media:search_image"),
            {"image": SimpleUploadedFile("q.png", b"synthhold-bytes", content_type="image/png")},
            **headers,
        )

    def _post_text(self, client, *, csrf_header=True):
        headers = {}
        if csrf_header and "csrftoken" in client.cookies:
            headers["HTTP_X_CSRFTOKEN"] = client.cookies["csrftoken"].value
        return client.post(
            reverse("media:search_text"),
            data='{"text":"synthhold","limit":5}',
            content_type="application/json",
            **headers,
        )

    def test_h07_endpoints_always_unavailable(self):
        """anonymous / user / staff x DEBUG True/False x valid CSRF / no CSRF."""
        actors = (None, self.user, self.staff)
        for debug in (True, False):
            for actor in actors:
                for with_csrf in (True, False):
                    with self.subTest(debug=debug, actor=getattr(actor, "username", None), csrf=with_csrf):
                        with override_settings(DEBUG=debug):
                            client = Client(enforce_csrf_checks=True)
                            if actor is not None:
                                client.force_login(actor)
                            client.get("/en/discover/")  # obtain a genuine CSRF cookie
                            for send in (self._post_image, self._post_text):
                                response = send(client, csrf_header=with_csrf)
                                # Valid CSRF reaches the view -> hold 503.
                                # Missing CSRF is rejected earlier by CsrfViewMiddleware (403).
                                self.assertEqual(response.status_code, 503 if with_csrf else 403)
                                if with_csrf:
                                    self.assertEqual(
                                        response.json(),
                                        {
                                            "error": "embedding_provider_not_configured",
                                            "detail": "A production embedding provider is not configured.",
                                        },
                                    )
                                self.assertNoMediaDisclosure(response)

    def test_h08_view_does_not_parse_body_or_build_service_during_hold(self):
        factory = RequestFactory()
        for view, request in (
            (
                media_api.search_by_image,
                factory.post(
                    "/api/media/search/image/",
                    {"image": SimpleUploadedFile("q.png", b"x", content_type="image/png")},
                ),
            ),
            (
                media_api.search_by_text,
                factory.post(
                    "/api/media/search/text/",
                    data='{"text":"x"}',
                    content_type="application/json",
                ),
            ),
        ):
            with self.subTest(view=view.__name__), override_settings(DEBUG=True), mock.patch.object(
                type(request), "_load_post_and_files", side_effect=AssertionError("POST/FILES parsed")
            ), mock.patch.object(
                type(request), "body", new_callable=mock.PropertyMock, side_effect=AssertionError("body read")
            ), mock.patch.object(
                media_api, "MediaSimilarityService", side_effect=AssertionError("service built")
            ) as service_spy:
                response = view(request)
                self.assertEqual(response.status_code, 503)
                service_spy.assert_not_called()

    def test_h08_control_spy_detects_parsing_when_hold_is_lifted(self):
        """Negative control: without the hold the same spy must fire."""
        request = RequestFactory().post(
            "/api/media/search/image/",
            {"image": SimpleUploadedFile("q.png", b"x", content_type="image/png")},
        )
        with override_settings(DEBUG=True), mock.patch.object(
            media_api, "MEDIA_SIMILARITY_API_HOLD", False
        ), mock.patch.object(
            type(request), "_load_post_and_files", side_effect=AssertionError("POST/FILES parsed")
        ), mock.patch.object(
            media_api, "MediaSimilarityService", return_value=mock.Mock()
        ):
            with self.assertRaisesMessage(AssertionError, "POST/FILES parsed"):
                media_api.search_by_image(request)

    def test_hold_flag_is_enabled(self):
        self.assertIs(media_api.MEDIA_SIMILARITY_API_HOLD, True)
        with override_settings(DEBUG=True):
            self.assertIsNone(media_api._service())
