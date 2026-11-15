"""Mock-only tests of the separately authenticated read-only Render API reader."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from config.tests.test_c02_resource_attestation import DB, SERVICE, RUNTIME, SHA
from scripts.c02_tests import verify_render_control_plane as reader


class RenderApiReadOnlyTests(TestCase):
    def test_missing_token_fails_before_http(self):
        with self.assertRaisesRegex(ValueError, "RENDER_API_KEY"):
            reader._fetch_json("/postgres/example", "")

    def test_read_only_endpoints_and_independent_metadata(self):
        def fake_read(path, token):
            self.assertEqual(token, "local-token-not-real")
            if path == "/postgres/dpg-dagru1h42hec73eqr960-a":
                return {"postgres": deepcopy(DB)}
            if path == "/services/srv-dadn07eq1p3s73eccau0":
                return {"service": deepcopy(SERVICE)}
            raise AssertionError("Unexpected Render API endpoint")
        with patch.object(reader, "_fetch_json", side_effect=fake_read) as getter:
            result = reader.run(deepcopy(RUNTIME), SHA, "local-token-not-real")
        self.assertEqual(getter.call_count, 2)
        self.assertTrue(result["CONTROL_PLANE_METADATA_MATCH"])
        self.assertFalse(result["POSTGRES_BACKEND_RESOURCE_IDENTITY_PROVEN"])
        self.assertFalse(result["C02_MIGRATION_GO"])

    def test_invalid_response_shape_rejected(self):
        with self.assertRaises(ValueError):
            reader._unwrap([], "postgres")

    def test_different_resource_rejected_from_api(self):
        other = deepcopy(DB)
        other["id"] = "unrelated-resource"
        with patch.object(reader, "_fetch_json", side_effect=[
            {"postgres": other},
            {"service": deepcopy(SERVICE)},
        ]):
            from django.core.management.base import CommandError
            with self.assertRaises(CommandError):
                reader.run(deepcopy(RUNTIME), SHA, "fixture-token")
