import json
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse


OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi-v1.json"
EXPECTED_PATHS = {
    "/api/search/",
    "/api/verification/product/{id}/",
    "/api/verification/library/{id}/",
    "/api/reputation/user/{id}/",
    "/api/reputation/user/{id}/{domain}/{method_code}/",
    "/api/reputation/{id}/",
    "/api/media/search/text/",
    "/api/media/search/image/",
}


class APIContractTests(SimpleTestCase):
    def test_openapi_contract_is_valid_json_and_tracks_current_surface(self):
        document = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

        self.assertEqual(document["openapi"], "3.1.0")
        self.assertEqual(document["info"]["version"], "1.0.0")
        self.assertEqual(set(document["paths"]), EXPECTED_PATHS)

    def test_verification_summaries_are_get_only(self):
        product_url = reverse("verification:product_summary", kwargs={"pk": 999999})
        library_url = reverse("verification:library_summary", kwargs={"pk": 999999})

        self.assertEqual(self.client.post(product_url).status_code, 405)
        self.assertEqual(self.client.post(library_url).status_code, 405)

    def test_documented_routes_reverse_to_current_paths(self):
        self.assertEqual(reverse("search:unified"), "/api/search/")
        self.assertEqual(
            reverse("verification:product_summary", kwargs={"pk": 7}),
            "/api/verification/product/7/",
        )
        self.assertEqual(
            reverse("verification:library_summary", kwargs={"pk": 7}),
            "/api/verification/library/7/",
        )
        self.assertEqual(
            reverse("core:public-reputation-list", kwargs={"user_id": 7}),
            "/api/reputation/user/7/",
        )
        self.assertEqual(
            reverse(
                "core:public-reputation-context",
                kwargs={"user_id": 7, "domain": "knowledge", "method_code": "peer"},
            ),
            "/api/reputation/user/7/knowledge/peer/",
        )
        self.assertEqual(
            reverse("core:reputation-detail", kwargs={"user_id": 7}),
            "/api/reputation/7/",
        )
        self.assertEqual(reverse("media:search_text"), "/api/media/search/text/")
        self.assertEqual(reverse("media:search_image"), "/api/media/search/image/")
