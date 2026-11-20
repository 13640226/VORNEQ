"""Regression: R2 signed downloads must be SigV4 and strictly verified.

Root cause of the Staging mock E2E failure: without an explicit signature
version/region, botocore presigned GET URLs with legacy SigV2 query auth,
which Cloudflare R2 rejects, while header-signed PUT/HEAD calls succeeded.
No network: S3Storage only presigns locally; HTTP is replaced by fakes.
"""
import hashlib
import importlib.util
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.ai_core.image_generation.storage import durable_storage_ready
from apps.core import staging_image_mock_e2e as e2e
from config.image_storage import InvalidImageStorage, image_storage_options

HAS_BOTO = importlib.util.find_spec("boto3") is not None
ENDPOINT = "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com"
R2_HOST = "0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com"
KEY = "ai-generated/7/" + "a" * 32 + ".png"
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 64
DIGEST = hashlib.sha256(PNG).hexdigest()
CRED = "TESTKEY%2F20261120%2Fauto%2Fs3%2Faws4_request"


def options(**over):
    base = image_storage_options(bucket=e2e.BUCKET, endpoint_url=ENDPOINT,
                                 access_key="AKIATESTONLY", secret_key="test-secret-only")
    base.update(over)
    return base


def sigv4(path=None, host=R2_HOST, cred=CRED, extra=""):
    return ("https://{}{}?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential={}"
            "&X-Amz-Date=20261120T170000Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host"
            "&X-Amz-Signature=abc{}").format(host, path or "/{}/{}".format(e2e.BUCKET, KEY),
                                            cred, extra)


@skipUnless(HAS_BOTO, "boto3 is installed in CI via django-storages[s3]")
class PresignedUrlFormatTests(SimpleTestCase):
    def url(self, opts):
        from storages.backends.s3 import S3Storage
        return S3Storage(**opts).url(KEY)

    def test_configured_options_presign_r2_sigv4(self):
        url = self.url(options())
        e2e.check_signed_url(url, endpoint_host=R2_HOST)
        self.assertIn("X-Amz-Algorithm=AWS4-HMAC-SHA256", url)
        self.assertIn("%2Fauto%2Fs3%2Faws4_request", url)
        self.assertNotIn("AWSAccessKeyId=", url)

    def test_previous_options_presign_sigv2_and_are_rejected(self):
        legacy = {k: v for k, v in options().items()
                  if k not in ("signature_version", "region_name", "addressing_style")}
        url = self.url(legacy)
        self.assertIn("AWSAccessKeyId=", url)  # the failing Staging configuration
        with self.assertRaisesMessage(e2e.Aborted, "legacy SigV2"):
            e2e.check_signed_url(url, endpoint_host=R2_HOST)


class StorageOptionTests(SimpleTestCase):
    def test_options_pin_sigv4_region_and_private_access(self):
        opts = options()
        self.assertEqual((opts["signature_version"], opts["region_name"],
                          opts["addressing_style"]), ("s3v4", "auto", "path"))
        self.assertEqual((opts["default_acl"], opts["querystring_auth"],
                          opts["custom_domain"], opts["file_overwrite"]),
                         ("private", True, None, False))

    def test_invalid_endpoints_still_rejected(self):
        for endpoint in ("http://acct.r2.cloudflarestorage.com", "https://evil.example",
                         "https://user:pw@acct.r2.cloudflarestorage.com",
                         "https://acct.r2.cloudflarestorage.com?x=1"):
            with self.subTest(endpoint), self.assertRaises(InvalidImageStorage):
                image_storage_options(bucket="b", endpoint_url=endpoint,
                                      access_key="a", secret_key="s")

    def test_sigv2_configuration_is_not_durable_ready(self):
        stores = {"ai_images": {"BACKEND": "storages.backends.s3.S3Storage",
                                "OPTIONS": options()}}
        with override_settings(STORAGES=stores):
            self.assertTrue(durable_storage_ready())
        stores["ai_images"]["OPTIONS"] = options(signature_version=None)
        with override_settings(STORAGES=stores):
            self.assertFalse(durable_storage_ready())


class SignedUrlShapeTests(SimpleTestCase):
    def test_valid_sigv4_url_passes(self):
        e2e.check_signed_url(sigv4(), endpoint_host=R2_HOST)

    def test_rejected_shapes(self):
        cases = {
            "other host": sigv4(host="other.r2.cloudflarestorage.com"),
            "lookalike host": sigv4(host=R2_HOST + ".evil.example"),
            "http": sigv4().replace("https://", "http://"),
            "port": sigv4(host=R2_HOST + ":8443"),
            "userinfo": sigv4(host="u:p@" + R2_HOST),
            "other bucket": sigv4(path="/other-bucket/" + KEY),
            "outside prefix": sigv4(path="/{}/private/x.png".format(e2e.BUCKET)),
            "us-east-1 scope": sigv4(cred=CRED.replace("auto", "us-east-1")),
            "sigv2 mixed in": sigv4(extra="&AWSAccessKeyId=AKIA&Signature=x"),
            "duplicate param": sigv4(extra="&X-Amz-Signature=other"),
            "unsigned": sigv4().split("?", 1)[0],
        }
        for name, url in cases.items():
            with self.subTest(name), self.assertRaises(e2e.Aborted):
                e2e.check_signed_url(url, endpoint_host=R2_HOST)


class VerifyDownloadTests(SimpleTestCase):
    def verify(self, download):
        e2e.verify_signed_download(download, DIGEST)

    def test_valid_png_and_digest_pass(self):
        self.verify(e2e.Download(200, "image/png", PNG))

    def test_failures_have_specific_safe_reasons(self):
        cases = {
            "rejected by storage": e2e.Download(
                403, "application/xml",
                b"<Error><Code>SignatureDoesNotMatch</Code><Message>X-Amz-Signature=secret"
                b"</Message></Error>"),
            "digest mismatch": e2e.Download(200, "image/png", PNG + b"!"),
            "wrong content type": e2e.Download(200, "text/html", b"<html>login</html>"),
            "is not a PNG": e2e.Download(200, "image/png", b"<html>login</html>"),
            "redirected": e2e.Download(302, "text/html", b""),
            "exceeds size limit": e2e.Download(200, "image/png", PNG, truncated=True),
        }
        for reason, download in cases.items():
            with self.subTest(reason), self.assertRaises(e2e.Aborted) as ctx:
                self.verify(download)
            message = str(ctx.exception)
            self.assertIn(reason, message)
            self.assertNotIn("X-Amz", message)
            self.assertNotIn("secret", message)
        with self.assertRaises(e2e.Aborted) as ctx:
            self.verify(cases["rejected by storage"])
        self.assertIn("status=403", str(ctx.exception))
        self.assertIn("r2_code=SignatureDoesNotMatch", str(ctx.exception))

    def test_non_download_result_rejected(self):
        with self.assertRaises(e2e.Aborted):
            e2e.verify_signed_download((200, PNG), DIGEST)


class FakeResponse:
    def __init__(self, status=200, ctype="image/png", body=PNG):
        self.status, self.ctype, self.body = status, ctype, body

    def getheader(self, name, default=None):
        return self.ctype if name == "Content-Type" else default

    def read(self, limit):
        return self.body[:limit]


class FakeConnection:
    response = FakeResponse()
    error = None
    calls = []

    def __init__(self, host, timeout, context):
        FakeConnection.calls.append(("connect", host, timeout))

    def request(self, method, path, headers):
        FakeConnection.calls.append(("request", method))
        if FakeConnection.error:
            raise FakeConnection.error

    def getresponse(self):
        return FakeConnection.response

    def close(self):
        FakeConnection.calls.append(("close",))


class FetchUrlTests(SimpleTestCase):
    def setUp(self):
        FakeConnection.response, FakeConnection.error, FakeConnection.calls = \
            FakeResponse(), None, []
        p = patch("apps.core.staging_image_mock_e2e.http.client.HTTPSConnection", FakeConnection)
        p.start()
        self.addCleanup(p.stop)

    def test_success_returns_download_and_closes(self):
        d = e2e.fetch_url(sigv4())
        self.assertEqual((d.status, d.content_type, d.body, d.truncated),
                         (200, "image/png", PNG, False))
        self.assertEqual(FakeConnection.calls[0], ("connect", R2_HOST, 10))
        self.assertEqual(FakeConnection.calls[-1], ("close",))

    def test_oversized_body_is_truncated_and_flagged(self):
        FakeConnection.response = FakeResponse(body=b"x" * (e2e.MAX_PNG_BYTES + 5))
        d = e2e.fetch_url(sigv4())
        self.assertTrue(d.truncated)
        self.assertEqual(len(d.body), e2e.MAX_PNG_BYTES)
        with self.assertRaisesMessage(e2e.Aborted, "exceeds size limit"):
            e2e.verify_signed_download(d, DIGEST)

    def test_redirect_is_not_followed(self):
        FakeConnection.response = FakeResponse(302, "text/html", b"")
        d = e2e.fetch_url(sigv4())
        self.assertEqual(d.status, 302)
        self.assertEqual([c[0] for c in FakeConnection.calls], ["connect", "request", "close"])

    def test_timeout_and_disconnect_are_safe_aborts(self):
        import http.client
        for error in (TimeoutError("t"), ConnectionResetError("r"),
                      http.client.RemoteDisconnected("d")):
            FakeConnection.error = error
            with self.subTest(type(error).__name__), self.assertRaises(e2e.Aborted) as ctx:
                e2e.fetch_url(sigv4())
            self.assertIn("transport error: " + type(error).__name__, str(ctx.exception))
            self.assertNotIn("X-Amz", str(ctx.exception))

    def test_foreign_host_never_connects(self):
        with self.assertRaises(e2e.Aborted):
            e2e.fetch_url("https://example.com/x.png?X-Amz-Signature=1")
        self.assertEqual(FakeConnection.calls, [])


class DiagnoseTests(SimpleTestCase):
    def run_diag(self, download):
        lines = []
        with patch("apps.ai_core.image_generation.storage.image_storage") as storage:
            storage.return_value.url.side_effect = lambda key: sigv4(
                path="/{}/{}".format(e2e.BUCKET, key))
            result = e2e.diagnose_signed_url(out=lines.append, fetch=lambda url: download,
                                             endpoint_host=R2_HOST)
        self.assertFalse(any("X-Amz" in line or "http" in line for line in lines))
        return result, lines

    def test_nosuchkey_means_signature_accepted(self):
        result, lines = self.run_diag(e2e.Download(
            404, "application/xml", b"<Error><Code>NoSuchKey</Code></Error>"))
        self.assertTrue(result)
        self.assertIn("R2_SIGNED_URL_RESULT: SIGNATURE_ACCEPTED", lines)

    def test_signature_error_is_reported_safely(self):
        result, lines = self.run_diag(e2e.Download(
            403, "application/xml", b"<Error><Code>SignatureDoesNotMatch</Code></Error>"))
        self.assertFalse(result)
        self.assertIn("R2_SIGNED_GET status=403 content_type=application/xml bytes=49 "
                      "r2_code=SignatureDoesNotMatch", lines)
        self.assertIn("R2_SIGNED_URL_RESULT: REJECTED", lines)
