"""Image history and download tests. Synthetic data, in-memory storage, no network."""
import hashlib
import json
import sys
import types
import uuid
from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.ai_core.image_generation import gallery
from apps.ai_core.image_generation.providers import MockImageProvider, OpenAIImageProvider
from apps.ai_core.image_generation.storage import image_storage
from apps.ai_core.models import AIImageDailyQuota, AIImageJob

STORES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "ai_images": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}
FLAGS = {
    "VORNEQ_ENV": "development",
    "VORNEQ_AI_IMAGE_ENABLED": True,
    "VORNEQ_AI_IMAGE_PROVIDER": "mock",
    "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False,
    "VORNEQ_AI_IMAGE_MODEL": "gpt-image-2.6-flare",
    "VORNEQ_AI_EMERGENCY_STOP": False,
    "STORAGES": STORES,
}
HISTORY_KEYS = {"id", "status", "model", "size", "created_at", "mock"}


def png_bytes(color=(10, 20, 30), size=(8, 6)):
    out = BytesIO()
    Image.new("RGB", size, color).save(out, format="PNG")
    return out.getvalue()


def key_for(job):
    return "ai-generated/{}/{}.png".format(job.owner_id, job.pk.hex)


@override_settings(**FLAGS)
class GalleryBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="gallery-owner", password="safe-test")
        cls.other = user_model.objects.create_user(username="gallery-other", password="safe-test")

    def setUp(self):
        self.client.force_login(self.owner)
        # Any provider SDK or ledger path reached by these read-only views is a failure.
        self.sdk_calls = []

        def forbidden(*args, **kwargs):
            self.sdk_calls.append("OpenAI")
            raise AssertionError("PAID_SDK_CONSTRUCTED")

        module = types.ModuleType("openai")
        module.OpenAI = forbidden
        sdk = patch.dict(sys.modules, {"openai": module})
        sdk.start()
        self.addCleanup(sdk.stop)
        self.provider_mocks = [
            patch.object(MockImageProvider, "generate", side_effect=AssertionError("PROVIDER_CALLED")),
            patch.object(OpenAIImageProvider, "generate", side_effect=AssertionError("PROVIDER_CALLED")),
        ]
        self.ledger_mocks = [
            patch("apps.ai_ledger.service." + name, side_effect=AssertionError("LEDGER_CALLED"))
            for name in ("reserve", "reserve_with_config", "reserve_prepaid_image", "settle", "release")
        ]
        for item in self.provider_mocks + self.ledger_mocks:
            item.start()
            self.addCleanup(item.stop)
        self.jobs_before = AIImageJob.objects.count()
        self.quota_before = list(AIImageDailyQuota.objects.values_list("pk", "submitted"))

    def tearDown(self):
        self.assertEqual(self.sdk_calls, [])
        self.assertEqual(AIImageJob.objects.count(), self.jobs_before)
        self.assertEqual(list(AIImageDailyQuota.objects.values_list("pk", "submitted")), self.quota_before)

    def make_job(self, owner=None, *, status=AIImageJob.STATUS_COMPLETED, store=True,
                 content=None, created_at=None, digest=True):
        owner = owner or self.owner
        job = AIImageJob.objects.create(
            owner=owner, prompt="", prompt_digest="d" * 64, model_id="mock",
            image_size="1024x1024", provider="mock", status=status, is_mock=True,
        )
        data = content if content is not None else png_bytes()
        if status == AIImageJob.STATUS_COMPLETED:
            job.storage_key = key_for(job)
            if digest:
                job.image_digest = hashlib.sha256(data).hexdigest()
            job.save()
            if store:
                image_storage().save(job.storage_key, ContentFile(data))
        if created_at is not None:
            AIImageJob.objects.filter(pk=job.pk).update(created_at=created_at)
            job.refresh_from_db()
        # Seed rows are fixtures, not submissions.
        self.jobs_before += 1
        return job

    def history(self, **params):
        return self.client.get(reverse("ai_core:image-history"), params)

    def download_url(self, job):
        return reverse("ai_core:image-job-download", args=[job.pk])


class HistoryTests(GalleryBase):
    def test_anonymous_denied_with_existing_contract(self):
        self.client.logout()
        response = self.history()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "authentication_required"})

    @override_settings(VORNEQ_AI_IMAGE_ENABLED=False)
    def test_unauthorized_actor_denied_with_existing_contract(self):
        response = self.history()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "unavailable"})

    def test_owner_sees_only_own_completed_images_metadata_only(self):
        mine = self.make_job()
        self.make_job(self.other)
        self.make_job(status=AIImageJob.STATUS_QUEUED)
        self.make_job(status=AIImageJob.STATUS_FAILED)
        response = self.history()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["id"] for item in body["results"]], [str(mine.pk)])
        self.assertEqual(set(body["results"][0]), HISTORY_KEYS)
        self.assertEqual(body["next_cursor"], None)
        self.assertIs(body["has_more"], False)
        text = response.content.decode()
        for forbidden in ("storage_key", "ai-generated", "prompt", "reservation", "ledger", "image_url", "digest"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_history_does_not_generate_signed_urls(self):
        self.make_job()
        with patch.object(type(image_storage()), "url", side_effect=AssertionError("SIGNED")):
            self.assertEqual(self.history().status_code, 200)

    def test_other_users_history_is_isolated(self):
        self.make_job(self.other)
        self.assertEqual(self.history().json()["results"], [])

    def test_pagination_is_stable_without_duplicates_or_gaps(self):
        base = timezone.now() - timedelta(hours=1)
        jobs = [self.make_job(created_at=base + timedelta(minutes=i)) for i in range(7)]
        expected = [str(job.pk) for job in sorted(jobs, key=lambda j: (j.created_at, j.pk), reverse=True)]
        seen, cursor = [], None
        for _ in range(10):
            params = {"limit": "3"}
            if cursor:
                params["cursor"] = cursor
            body = self.history(**params).json()
            seen += [item["id"] for item in body["results"]]
            cursor = body["next_cursor"]
            self.assertEqual(body["has_more"], cursor is not None)
            if not cursor:
                break
        self.assertEqual(seen, expected)
        self.assertEqual(len(set(seen)), 7)

    def test_equal_timestamps_paginate_by_uuid(self):
        stamp = timezone.now() - timedelta(minutes=5)
        jobs = [self.make_job(created_at=stamp) for _ in range(5)]
        expected = [str(j.pk) for j in sorted(jobs, key=lambda j: j.pk, reverse=True)]
        seen, cursor = [], None
        for _ in range(10):
            params = {"limit": "2"}
            if cursor:
                params["cursor"] = cursor
            body = self.history(**params).json()
            seen += [item["id"] for item in body["results"]]
            cursor = body["next_cursor"]
            if not cursor:
                break
        self.assertEqual(seen, expected)

    def test_new_rows_do_not_duplicate_older_pages(self):
        base = timezone.now() - timedelta(hours=2)
        for i in range(4):
            self.make_job(created_at=base + timedelta(minutes=i))
        first = self.history(limit="2").json()
        self.make_job(created_at=timezone.now())
        second = self.history(limit="2", cursor=first["next_cursor"]).json()
        self.assertFalse({r["id"] for r in first["results"]} & {r["id"] for r in second["results"]})

    def test_cursor_from_another_user_is_rejected(self):
        for _ in range(3):
            self.make_job(self.other)
            self.make_job()
        theirs = self.client_for(self.other).get(reverse("ai_core:image-history"), {"limit": "1"}).json()
        response = self.history(cursor=theirs["next_cursor"])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "invalid_cursor"})

    def client_for(self, user):
        from django.test import Client
        client = Client()
        client.force_login(user)
        return client

    def _signed(self, payload):
        return signing.dumps(payload, salt=gallery.CURSOR_SALT, compress=True)

    def test_invalid_cursors_are_rejected_not_reset_to_first_page(self):
        self.make_job()
        good = {"u": str(self.owner.pk), "t": timezone.now().isoformat(), "p": str(uuid.uuid4())}
        bad = [
            "garbage", "a" * (gallery.MAX_CURSOR_LENGTH + 1), "",
            signing.dumps(good, salt="wrong-salt"),
            self._signed({**good, "p": "not-a-uuid"}),
            self._signed({**good, "p": 12}),
            self._signed({**good, "t": "2026-01-01T00:00:00"}),  # naive timestamp
            self._signed({**good, "t": "yesterday"}),
            self._signed({**good, "extra": "x"}),
            self._signed({k: v for k, v in good.items() if k != "p"}),
            self._signed([1, 2, 3]),
        ]
        for token in bad:
            response = self.history(cursor=token)
            self.assertEqual(response.status_code, 400, token[:20])
            self.assertEqual(response.json(), {"error": "invalid_cursor"})

    def test_valid_cursor_signed_by_the_view_is_accepted(self):
        good = {"u": str(self.owner.pk), "t": timezone.now().isoformat(), "p": str(uuid.uuid4())}
        self.assertEqual(self.history(cursor=self._signed(good)).status_code, 200)

    def test_limit_validation(self):
        for value in ("0", "51", "-1", "x", "1.5", "9999", ""):
            self.assertEqual(self.history(limit=value).status_code, 400, value)
        self.assertEqual(self.history(limit="50").status_code, 200)

    def test_history_rejects_post(self):
        self.assertEqual(self.client.post(reverse("ai_core:image-history")).status_code, 405)


class DownloadTests(GalleryBase):
    def test_completed_download_returns_original_png(self):
        data = png_bytes((200, 10, 10), (32, 16))
        job = self.make_job(content=data)
        response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="VORNEQ-image-{}.png"'.format(job.pk),
        )
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Content-Length"], str(len(data)))
        self.assertNotIn("ai-generated", str(dict(response.items())))

    def test_anonymous_and_unauthorized_contracts(self):
        job = self.make_job()
        self.client.logout()
        self.assertEqual(self.client.get(self.download_url(job)).status_code, 401)
        self.client.force_login(self.owner)
        with override_settings(VORNEQ_AI_IMAGE_ENABLED=False):
            response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "unavailable"})

    def test_cross_user_download_is_404_even_with_known_uuid(self):
        job = self.make_job(self.other)
        response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "not_found"})

    def test_non_completed_job_is_not_downloadable(self):
        for status in (AIImageJob.STATUS_QUEUED, AIImageJob.STATUS_RUNNING,
                       AIImageJob.STATUS_FAILED, AIImageJob.STATUS_UNCERTAIN):
            job = self.make_job(status=status)
            self.assertEqual(self.client.get(self.download_url(job)).status_code, 404, status)

    def test_unknown_uuid_is_404(self):
        response = self.client.get(reverse("ai_core:image-job-download", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_row_with_foreign_storage_key_is_never_served(self):
        victim = self.make_job(self.other, content=png_bytes((1, 2, 3)))
        job = self.make_job()
        AIImageJob.objects.filter(pk=job.pk).update(storage_key=key_for(victim))
        self.assertEqual(self.client.get(self.download_url(job)).status_code, 404)

    def test_missing_storage_object_is_handled_without_leaking_key(self):
        job = self.make_job(store=False)
        response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "storage_unavailable"})
        self.assertNotIn("ai-generated", response.content.decode())
        self.assertNotIn(job.pk.hex, response.content.decode())

    def test_unsupported_mime_is_rejected(self):
        out = BytesIO()
        Image.new("RGB", (4, 4)).save(out, format="JPEG")
        job = self.make_job(content=out.getvalue())
        self.assertEqual(self.client.get(self.download_url(job)).status_code, 502)
        job = self.make_job(content=b"<html>not an image</html>")
        self.assertEqual(self.client.get(self.download_url(job)).status_code, 502)

    def test_digest_mismatch_is_rejected(self):
        job = self.make_job()
        AIImageJob.objects.filter(pk=job.pk).update(image_digest="0" * 64)
        self.assertEqual(self.client.get(self.download_url(job)).status_code, 502)

    def test_size_limit_enforced_before_reading(self):
        job = self.make_job()
        with patch.object(gallery, "MAX_DOWNLOAD_BYTES", 10), \
                patch.object(type(image_storage()), "open", side_effect=AssertionError("READ")):
            response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 502)

    def test_size_limit_enforced_while_reading_when_declared_size_lies(self):
        job = self.make_job()
        handle = MagicMock()
        handle.read.side_effect = lambda n: b"x" * n
        with patch.object(type(image_storage()), "size", return_value=gallery.MAX_DOWNLOAD_BYTES), \
                patch.object(type(image_storage()), "open", return_value=handle):
            response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 502)
        handle.close.assert_called_once()
        self.assertTrue(all(call.args[0] <= gallery.READ_CHUNK_BYTES for call in handle.read.call_args_list))

    def test_stream_is_fully_consumed_in_bounded_chunks_and_closed(self):
        data = png_bytes((5, 5, 5), (64, 64))
        job = self.make_job(content=data)
        raw = BytesIO(data)
        handle = MagicMock()
        handle.read.side_effect = raw.read
        with patch.object(gallery, "READ_CHUNK_BYTES", 7), \
                patch.object(type(image_storage()), "open", return_value=handle):
            response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)
        self.assertEqual(raw.tell(), len(data))
        handle.close.assert_called_once()
        self.assertTrue(all(call.args[0] <= 7 for call in handle.read.call_args_list))

    def test_handle_is_closed_when_read_fails(self):
        job = self.make_job()
        handle = MagicMock()
        handle.read.side_effect = OSError("connection reset")
        with patch.object(type(image_storage()), "open", return_value=handle):
            response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 502)
        handle.close.assert_called_once()
        self.assertNotIn("connection reset", response.content.decode())

    def test_close_failure_does_not_mask_success(self):
        data = png_bytes()
        job = self.make_job(content=data)
        raw = BytesIO(data)
        handle = MagicMock()
        handle.read.side_effect = raw.read
        handle.close.side_effect = OSError("close failed")
        with patch.object(type(image_storage()), "open", return_value=handle):
            self.assertEqual(self.client.get(self.download_url(job)).status_code, 200)

    def test_storage_exceptions_are_mapped_without_detail(self):
        job = self.make_job()
        secret = "bucket-credentials-leak"
        for target in ("size", "open"):
            with patch.object(type(image_storage()), target, side_effect=RuntimeError(secret)):
                response = self.client.get(self.download_url(job))
            self.assertEqual(response.status_code, 502, target)
            self.assertNotIn(secret, response.content.decode())

    def test_read_deadline_is_enforced(self):
        job = self.make_job()
        with patch.object(gallery, "READ_DEADLINE_SECONDS", -1.0):
            response = self.client.get(self.download_url(job))
        self.assertEqual(response.status_code, 502)

    def test_download_does_not_sign_urls(self):
        job = self.make_job()
        with patch.object(type(image_storage()), "url", side_effect=AssertionError("SIGNED")):
            self.assertEqual(self.client.get(self.download_url(job)).status_code, 200)

    def test_download_rejects_post(self):
        job = self.make_job()
        self.assertEqual(self.client.post(self.download_url(job)).status_code, 405)


class PreservedContractTests(GalleryBase):
    """PR 1 endpoints keep working next to the new routes."""

    def test_active_latest_and_detail_endpoints_unchanged(self):
        job = self.make_job()
        base = reverse("ai_core:image-jobs")
        self.assertEqual(self.client.get(base, {"latest": "1"}).json(), {"id": str(job.pk)})
        self.assertEqual(self.client.get(base, {"active": "1"}).json(), {"results": []})
        detail = self.client.get(reverse("ai_core:image-job-detail", args=[job.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], str(job.pk))
        self.assertIn("image_url", detail.json())

    def test_history_route_is_not_swallowed_by_uuid_route(self):
        self.assertEqual(reverse("ai_core:image-history"), "/api/ai/v1/images/jobs/history/")
        self.assertEqual(self.client.get(reverse("ai_core:image-history")).status_code, 200)
