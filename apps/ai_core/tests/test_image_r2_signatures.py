"""Regression tests: R2 presigned URLs must use AWS SigV4, not SigV2."""
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase, override_settings

from apps.ai_core.image_generation.storage import durable_storage_ready


def _storage_config(*, signature="s3v4", expires=900):
    return {
        "ai_images": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": "test-private-bucket",
                "endpoint_url": "https://00000000000000000000000000000000.r2.cloudflarestorage.com",
                "access_key": "fake-r2-key",
                "secret_key": "fake-r2-secret",
                "default_acl": "private",
                "custom_domain": None,
                "querystring_auth": True,
                "signature_version": signature,
                "querystring_expire": expires,
            },
        },
    }


class R2SignatureTests(SimpleTestCase):
    def test_signature_v2_is_not_accepted_for_private_image_storage(self):
        with override_settings(STORAGES=_storage_config(signature="s3")):
            self.assertFalse(durable_storage_ready())

    def test_unsigned_links_are_not_considered_private(self):
        config = _storage_config()
        config["ai_images"]["OPTIONS"]["querystring_auth"] = False
        with override_settings(STORAGES=config):
            self.assertFalse(durable_storage_ready())

    def test_overlong_presigned_url_lifetime_is_not_accepted(self):
        with override_settings(STORAGES=_storage_config(expires=86400)):
            self.assertFalse(durable_storage_ready())

    def test_sigv4_private_storage_config_is_accepted(self):
        with override_settings(STORAGES=_storage_config()):
            self.assertTrue(durable_storage_ready())

    def test_sigv4_url_uses_aws4_hmac_sha256_without_network(self):
        from storages.backends.s3 import S3Storage
        instance = S3Storage(**_storage_config()["ai_images"]["OPTIONS"])
        url = instance.url("ai-generated/user-1/example.png")
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params.get("X-Amz-Algorithm"), ["AWS4-HMAC-SHA256"])
        self.assertEqual(params.get("X-Amz-Expires"), ["900"])
        self.assertEqual(len(params.get("X-Amz-Signature", [])), 1)
        self.assertNotIn("AWSAccessKeyId", params)
        self.assertTrue(url.startswith("https://"))
