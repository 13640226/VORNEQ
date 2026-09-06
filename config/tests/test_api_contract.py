import json
from pathlib import Path

import pytest
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


def test_openapi_contract_is_valid_json_and_tracks_current_surface():
    document = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    assert document["openapi"] == "3.1.0"
    assert document["info"]["version"] == "1.0.0"
    assert set(document["paths"]) == EXPECTED_PATHS


@pytest.mark.django_db
def test_verification_summaries_are_get_only(client):
    product_url = reverse("verification:product_summary", kwargs={"pk": 999999})
    library_url = reverse("verification:library_summary", kwargs={"pk": 999999})

    assert client.post(product_url).status_code == 405
    assert client.post(library_url).status_code == 405


def test_documented_routes_reverse_to_current_paths():
    assert reverse("search:unified") == "/api/search/"
    assert reverse("verification:product_summary", kwargs={"pk": 7}) == "/api/verification/product/7/"
    assert reverse("verification:library_summary", kwargs={"pk": 7}) == "/api/verification/library/7/"
    assert reverse("core:public-reputation-list", kwargs={"user_id": 7}) == "/api/reputation/user/7/"
    assert reverse(
        "core:public-reputation-context",
        kwargs={"user_id": 7, "domain": "knowledge", "method_code": "peer"},
    ) == "/api/reputation/user/7/knowledge/peer/"
    assert reverse("core:reputation-detail", kwargs={"user_id": 7}) == "/api/reputation/7/"
    assert reverse("media:search_text") == "/api/media/search/text/"
    assert reverse("media:search_image") == "/api/media/search/image/"
