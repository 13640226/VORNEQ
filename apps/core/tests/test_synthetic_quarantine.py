"""Isolated SQLite contract and behavior tests for quarantine v1."""
import copy
import hashlib
import os
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.content.models import Article, Category
from apps.core.synthetic_quarantine import (
    QuarantineRejected,
    _digest,
    apply_quarantine,
    prepare_manifest,
    revert_quarantine,
    register_signed_batch,
    signing_bytes,
)
from apps.media.models import MediaAsset
from apps.search.services import ArticleAdapter, LibraryItemAdapter, ProductAdapter
from library.models import LibraryItem
from marketplace.models import Product


class SyntheticQuarantineLocalTests(TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "VORNEQ_QUARANTINE_LOCAL_ONLY": "EXPLICIT_LOCAL_TEST",
            "DATABASE_URL": "",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        User = get_user_model()
        self.owner_private_key = Ed25519PrivateKey.generate()
        public_key = self.owner_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.anchor = {
            "status": "preapproved",
            "owner_account": "13640226",
            "authorization_reference": "OWNER_LOCAL_TEST_ONLY",
            "public_key_ed25519_hex": public_key.hex(),
            "fingerprint_sha256": hashlib.sha256(public_key).hexdigest(),
        }
        self.trust_setting = override_settings(
            VORNEQ_QUARANTINE_OWNER_TRUST_ANCHORS={"local-simulated-owner": self.anchor}
        )
        self.trust_setting.enable()
        self.addCleanup(self.trust_setting.disable)
        self.owner = User.objects.create_superuser(
            username="quarantine-local-owner", email="local-owner@example.invalid",
            password="local-test-only",
        )
        self.seller = User.objects.create_user(username="vorneq-benchmark-seed")
        self.smoke_seller = User.objects.create_user(username="vorneq-inspect-smoke")
        self.real_seller = User.objects.create_user(username="legitimate-seller")
        self.category = Category.objects.create(
            name="VORNEQ Benchmark", slug="vorneq-benchmark-category"
        )
        self.article = Article.objects.create(
            category=self.category, title="Benchmark Article",
            summary="synthetic", content="benchmark ai content",
            slug="vorneq-benchmark-article-000001",
            editorial_metadata={"benchmark_seed": True, "index": 1},
            is_published=True, published_at=timezone.now(),
        )
        self.product = Product.objects.create(
            seller=self.seller, title="Benchmark Product",
            slug="vorneq-benchmark-product-000001",
            status=Product.STATUS_APPROVED, is_published=True,
            published_at=timezone.now(),
        )
        self.smoke = Product.objects.create(
            seller=self.smoke_seller, title="Inspect Staging Smoke Product",
            slug="inspect-staging-smoke",
            status=Product.STATUS_APPROVED, is_published=True,
            published_at=timezone.now(),
        )
        self.library = LibraryItem.objects.create(
            title="Benchmark Library", slug="vorneq-benchmark-library-000001",
            author="VORNEQ Benchmark Seed", category="benchmark",
            content="benchmark text", is_published=True, published_at=timezone.now(),
        )
        self.media = MediaAsset.objects.create(
            media_type=MediaAsset.MediaType.IMAGE,
            title="VORNEQ Benchmark Media image 000001",
            file="benchmark/vorneq-benchmark-media-000001.jpg",
            mime_type="image/jpeg", byte_size=1024, width=1200, height=800,
            presentation_metadata={"benchmark_seed": True, "index": 1},
            is_active=True,
        )
        self.real_article = Article.objects.create(
            category=self.category, title="Genuine Article", summary="real",
            content="genuine text", slug="real-article-1",
            is_published=True, published_at=timezone.now(),
        )
        self.real_product = Product.objects.create(
            seller=self.real_seller, title="Genuine Product",
            slug="real-product-1", status=Product.STATUS_APPROVED,
            is_published=True, published_at=timezone.now(),
        )
        self.real_library = LibraryItem.objects.create(
            title="Genuine Library", slug="real-library-1",
            is_published=True, published_at=timezone.now(),
        )
        self.real_media = MediaAsset.objects.create(
            media_type=MediaAsset.MediaType.IMAGE,
            title="Genuine Media", file="legitimate/image.jpg",
            mime_type="image/jpeg", byte_size=1024, width=800, height=600,
            is_active=True,
        )
        self.ids = {
            "article": [self.article.pk],
            "product": [self.product.pk, self.smoke.pk],
            "library": [self.library.pk],
            "media": [self.media.pk],
        }

    def manifest(self):
        m = prepare_manifest(
            ids_by_kind=self.ids, actor=self.owner,
            batch_id=uuid.uuid4(), authorization_reference="OWNER_LOCAL_TEST_ONLY",
        )
        register_signed_batch(
            manifest=m,
            actor=self.owner,
            signature_hex=self.owner_private_key.sign(signing_bytes(m)).hex(),
            signing_key_id="local-simulated-owner",
        )
        return m

    def test_quarantine_and_reverse_preserves_every_field(self):
        m = self.manifest()
        original = {
            "article": (self.article.is_published, self.article.published_at, self.article.updated_at),
            "product": (self.product.is_published, self.product.status, self.product.published_at, self.product.updated_at),
            "library": (self.library.is_published, self.library.published_at, self.library.updated_at),
            "media": (self.media.is_active, self.media.updated_at),
        }
        self.assertEqual(apply_quarantine(manifest=m, actor=self.owner), 5)
        for obj in (self.article, self.product, self.smoke, self.library, self.media):
            obj.refresh_from_db()
        self.assertFalse(self.article.is_published)
        self.assertFalse(self.product.is_published)
        self.assertFalse(self.smoke.is_published)
        self.assertFalse(self.library.is_published)
        self.assertFalse(self.media.is_active)
        self.assertEqual(self.product.status, Product.STATUS_APPROVED)
        self.assertEqual(self.product.published_at, original["product"][2])
        self.assertEqual(self.article.updated_at, original["article"][2])
        # The public search adapters must hide fixtures without hiding genuine data.
        self.assertEqual(ArticleAdapter().get_queryset("Benchmark", {}).count(), 0)
        self.assertEqual(ProductAdapter().get_queryset("Benchmark", {}).count(), 0)
        self.assertEqual(LibraryItemAdapter().get_queryset("Benchmark", {}).count(), 0)
        self.assertEqual(ArticleAdapter().get_queryset("Genuine", {}).count(), 1)
        self.assertEqual(ProductAdapter().get_queryset("Genuine", {}).count(), 1)
        self.assertEqual(LibraryItemAdapter().get_queryset("Genuine", {}).count(), 1)
        self.assertTrue(self.real_media.is_active)
        self.assertEqual(
            AuditEvent.objects.filter(correlation_id=m["batch_id"]).count(), 5
        )
        self.assertEqual(revert_quarantine(manifest=m, actor=self.owner), 5)
        for obj in (self.article, self.product, self.smoke, self.library, self.media):
            obj.refresh_from_db()
        self.assertEqual(
            (self.article.is_published, self.article.published_at, self.article.updated_at),
            original["article"],
        )
        self.assertEqual(
            (self.product.is_published, self.product.status, self.product.published_at, self.product.updated_at),
            original["product"],
        )
        self.assertEqual(
            (self.library.is_published, self.library.published_at, self.library.updated_at),
            original["library"],
        )
        self.assertEqual((self.media.is_active, self.media.updated_at), original["media"])
        self.assertEqual(
            AuditEvent.objects.filter(correlation_id=m["batch_id"]).count(), 8
        )

    def test_manifest_tamper_is_rejected(self):
        m = self.manifest()
        m["rows"][0]["object_id"] = "wrong"
        with self.assertRaisesRegex(QuarantineRejected, "DIGEST"):
            apply_quarantine(manifest=m, actor=self.owner)
        self.assertTrue(self.article.is_published)

    def test_missing_id_is_rejected(self):
        self.ids["article"] = [uuid.uuid4()]
        with self.assertRaisesRegex(QuarantineRejected, "MISSING_ROW"):
            self.manifest()

    def test_non_synthetic_row_is_rejected(self):
        self.ids["article"] = [self.real_article.pk]
        with self.assertRaisesRegex(QuarantineRejected, "PROVENANCE"):
            self.manifest()
        self.assertTrue(self.real_article.is_published)

    def test_mixed_real_and_synthetic_rows_are_rejected(self):
        self.ids["product"].append(self.real_product.pk)
        with self.assertRaisesRegex(QuarantineRejected, "PROVENANCE"):
            self.manifest()

    def test_duplicate_id_is_rejected(self):
        self.ids["product"].append(self.product.pk)
        with self.assertRaisesRegex(QuarantineRejected, "DUPLICATE"):
            self.manifest()

    def test_count_tampering_is_rejected_even_with_new_digest(self):
        m = self.manifest()
        m["counts"]["product"] = 1
        body = {k: v for k, v in m.items() if k != "manifest_sha256"}
        m["manifest_sha256"] = _digest(body)
        with self.assertRaisesRegex(QuarantineRejected, "COUNTS"):
            apply_quarantine(manifest=m, actor=self.owner)

    def test_stale_timestamp_is_rejected(self):
        m = self.manifest()
        Product.objects.filter(pk=self.product.pk).update(
            updated_at=timezone.now() + timedelta(days=1)
        )
        with self.assertRaisesRegex(QuarantineRejected, "NONFLAG_FIELD_CHANGED"):
            apply_quarantine(manifest=m, actor=self.owner)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_published)
        self.assertEqual(AuditEvent.objects.filter(correlation_id=m["batch_id"]).count(), 1)

    def test_changed_moderation_is_rejected(self):
        m = self.manifest()
        Product.objects.filter(pk=self.product.pk).update(status=Product.STATUS_REJECTED)
        with self.assertRaisesRegex(QuarantineRejected, "NONFLAG_FIELD_CHANGED"):
            apply_quarantine(manifest=m, actor=self.owner)

    def test_environment_guard_rejects_unbound_db(self):
        m = self.manifest()
        with patch.dict(os.environ, {"VORNEQ_QUARANTINE_LOCAL_ONLY": ""}):
            with self.assertRaisesRegex(QuarantineRejected, "LOCAL_OPT_IN"):
                apply_quarantine(manifest=m, actor=self.owner)

    def test_non_superuser_cannot_execute(self):
        m = self.manifest()
        with self.assertRaises(PermissionDenied):
            apply_quarantine(manifest=m, actor=self.real_seller)

    def test_apply_replay_is_rejected(self):
        m = self.manifest()
        apply_quarantine(manifest=m, actor=self.owner)
        with self.assertRaisesRegex(QuarantineRejected, "STATE_OR_AUTHORITY"):
            apply_quarantine(manifest=m, actor=self.owner)

    def test_revert_without_apply_is_rejected(self):
        m = self.manifest()
        with self.assertRaisesRegex(QuarantineRejected, "STATE_OR_AUTHORITY"):
            revert_quarantine(manifest=m, actor=self.owner)

    def test_revert_replay_is_rejected(self):
        m = self.manifest()
        apply_quarantine(manifest=m, actor=self.owner)
        revert_quarantine(manifest=m, actor=self.owner)
        with self.assertRaisesRegex(QuarantineRejected, "STATE_OR_AUTHORITY"):
            revert_quarantine(manifest=m, actor=self.owner)

    def test_audit_failure_rolls_back_all_visibility_updates(self):
        m = self.manifest()
        with patch(
            "apps.core.synthetic_quarantine.record_audit_event",
            side_effect=RuntimeError("simulated append-only audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failure"):
                apply_quarantine(manifest=m, actor=self.owner)
        self.product.refresh_from_db()
        self.article.refresh_from_db()
        self.assertTrue(self.product.is_published)
        self.assertTrue(self.article.is_published)
        self.assertEqual(
            AuditEvent.objects.filter(correlation_id=m["batch_id"]).count(), 1
        )

    def test_rollback_detects_intervening_edit(self):
        m = self.manifest()
        apply_quarantine(manifest=m, actor=self.owner)
        Product.objects.filter(pk=self.product.pk).update(
            published_at=timezone.now() + timedelta(days=5)
        )
        with self.assertRaisesRegex(QuarantineRejected, "NONFLAG_FIELD_CHANGED"):
            revert_quarantine(manifest=m, actor=self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)

    @override_settings(STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_public_product_and_library_http_detail_denied_after_quarantine(self):
        m = self.manifest()
        # Establish routes exist and are public before fixture hold.
        product_url = reverse("marketplace:detail", kwargs={"slug": self.product.slug})
        library_url = reverse("library:detail", kwargs={"slug": self.library.slug})
        before_product = self.client.get(product_url)
        before_library = self.client.get(library_url)
        self.assertEqual(before_product.status_code, 200)
        self.assertEqual(before_library.status_code, 200)
        apply_quarantine(manifest=m, actor=self.owner)
        self.assertEqual(self.client.get(product_url).status_code, 404)
        self.assertEqual(self.client.get(library_url).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("marketplace:detail", kwargs={"slug": self.real_product.slug})).status_code,
            200,
        )

    def test_public_ai_retrieval_excludes_fixture_after_hold(self):
        from apps.ai_core.gateway import retrieve_public
        m = self.manifest()
        before = retrieve_public("Benchmark", "en")
        self.assertGreater(len(before), 0)
        apply_quarantine(manifest=m, actor=self.owner)
        self.assertEqual(len(retrieve_public("Benchmark", "en")), 0)
        self.assertGreater(len(retrieve_public("Genuine", "en")), 0)

    def test_audit_failure_during_revert_rolls_back_all_flags(self):
        from apps.audit.services import record_audit_event as actual_audit

        m = self.manifest()
        apply_quarantine(manifest=m, actor=self.owner)

        def fail_last_event(**kwargs):
            if kwargs["event_name"].endswith("revert_verified"):
                raise RuntimeError("local induced audit failure at revert")
            return actual_audit(**kwargs)

        with patch(
            "apps.core.synthetic_quarantine.record_audit_event",
            side_effect=fail_last_event,
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failure"):
                revert_quarantine(manifest=m, actor=self.owner)
        self.article.refresh_from_db()
        self.product.refresh_from_db()
        self.assertFalse(self.article.is_published)
        self.assertFalse(self.product.is_published)
        self.assertEqual(
            AuditEvent.objects.filter(correlation_id=m["batch_id"]).count(), 5
        )

    def test_spoofed_slug_without_provenance_is_denied(self):
        spoof = Article.objects.create(
            category=self.category,
            title="Synthetic-looking user article",
            slug="vorneq-benchmark-article-999999",
            summary="legitimate", content="real",
            editorial_metadata={}, is_published=True,
        )
        self.ids["article"].append(spoof.pk)
        with self.assertRaisesRegex(QuarantineRejected, "PROVENANCE"):
            self.manifest()
        spoof.refresh_from_db()
        self.assertTrue(spoof.is_published)

    def test_wrong_database_identity_is_denied(self):
        from django.test import override_settings
        m = self.manifest()
        with override_settings(VORNEQ_ENV="production"):
            with self.assertRaisesRegex(QuarantineRejected, "ENVIRONMENT"):
                apply_quarantine(manifest=m, actor=self.owner)
        self.assertTrue(self.article.is_published)

    def test_wrong_backup_reference_is_denied(self):
        with self.assertRaisesRegex(QuarantineRejected, "SCOPE_OR_AUTHORITY"):
            prepare_manifest(
                ids_by_kind=self.ids,
                actor=self.owner,
                batch_id=uuid.uuid4(),
                authorization_reference="OWNER_LOCAL_TEST_ONLY",
                backup_sha256="0" * 64,
            )

    def test_signed_batch_state_and_audit_are_atomic(self):
        from apps.core.models import SyntheticQuarantineBatch

        m = self.manifest()
        batch = SyntheticQuarantineBatch.objects.get(pk=m["batch_id"])
        self.assertEqual(batch.state, "registered")
        self.assertEqual(batch.manifest_sha256, m["manifest_sha256"])
        self.assertEqual(AuditEvent.objects.filter(correlation_id=m["batch_id"]).count(), 1)
        apply_quarantine(manifest=m, actor=self.owner)
        batch.refresh_from_db()
        self.assertEqual(batch.state, "held")
        self.assertIsNotNone(batch.held_at)
        self.assertEqual(AuditEvent.objects.filter(correlation_id=m["batch_id"]).count(), 5)
        revert_quarantine(manifest=m, actor=self.owner)
        batch.refresh_from_db()
        self.assertEqual(batch.state, "reverted")
        self.assertIsNotNone(batch.reverted_at)
        self.assertEqual(AuditEvent.objects.filter(correlation_id=m["batch_id"]).count(), 8)

    def test_missing_trusted_owner_key_rejects_registration(self):
        m = prepare_manifest(
            ids_by_kind=self.ids, actor=self.owner,
            batch_id=uuid.uuid4(), authorization_reference="OWNER_LOCAL_TEST_ONLY",
        )
        with override_settings(VORNEQ_QUARANTINE_OWNER_TRUST_ANCHORS={}):
            with self.assertRaisesRegex(QuarantineRejected, "ANCHOR_MISSING"):
                register_signed_batch(
                    manifest=m, actor=self.owner,
                    signature_hex=self.owner_private_key.sign(signing_bytes(m)).hex(),
                    signing_key_id="local-simulated-owner",
                )
        from apps.core.models import SyntheticQuarantineBatch
        self.assertFalse(SyntheticQuarantineBatch.objects.filter(pk=m["batch_id"]).exists())

    def test_forged_signature_fails(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        m = prepare_manifest(
            ids_by_kind=self.ids, actor=self.owner,
            batch_id=uuid.uuid4(), authorization_reference="OWNER_LOCAL_TEST_ONLY",
        )
        attacker_key = Ed25519PrivateKey.generate()
        with self.assertRaisesRegex(QuarantineRejected, "INVALID_OWNER_SIGNATURE"):
            register_signed_batch(
                manifest=m, actor=self.owner,
                signature_hex=attacker_key.sign(signing_bytes(m)).hex(),
                signing_key_id="local-simulated-owner",
            )

    def test_forged_fingerprint_fails(self):
        m = prepare_manifest(
            ids_by_kind=self.ids, actor=self.owner,
            batch_id=uuid.uuid4(), authorization_reference="OWNER_LOCAL_TEST_ONLY",
        )
        anchor = {**self.anchor, "fingerprint_sha256": "0" * 64}
        with override_settings(
            VORNEQ_QUARANTINE_OWNER_TRUST_ANCHORS={"local-simulated-owner": anchor}
        ):
            with self.assertRaisesRegex(QuarantineRejected, "FINGERPRINT_MISMATCH"):
                register_signed_batch(
                    manifest=m, actor=self.owner,
                    signature_hex=self.owner_private_key.sign(signing_bytes(m)).hex(),
                    signing_key_id="local-simulated-owner",
                )

    def test_unapproved_anchor_fails(self):
        m = prepare_manifest(
            ids_by_kind=self.ids, actor=self.owner,
            batch_id=uuid.uuid4(), authorization_reference="OWNER_LOCAL_TEST_ONLY",
        )
        anchor = {**self.anchor, "status": "pending"}
        with override_settings(
            VORNEQ_QUARANTINE_OWNER_TRUST_ANCHORS={"local-simulated-owner": anchor}
        ):
            with self.assertRaisesRegex(QuarantineRejected, "NOT_PREAPPROVED"):
                register_signed_batch(
                    manifest=m, actor=self.owner,
                    signature_hex=self.owner_private_key.sign(signing_bytes(m)).hex(),
                    signing_key_id="local-simulated-owner",
                )

    def test_registration_audit_failure_rolls_back_batch(self):
        from apps.core.models import SyntheticQuarantineBatch
        m = prepare_manifest(
            ids_by_kind=self.ids, actor=self.owner,
            batch_id=uuid.uuid4(), authorization_reference="OWNER_LOCAL_TEST_ONLY",
        )
        with patch(
            "apps.core.synthetic_quarantine.record_audit_event",
            side_effect=RuntimeError("induced failure during signed registration"),
        ):
            with self.assertRaisesRegex(RuntimeError, "induced failure"):
                register_signed_batch(
                    manifest=m, actor=self.owner,
                    signature_hex=self.owner_private_key.sign(signing_bytes(m)).hex(),
                    signing_key_id="local-simulated-owner",
                )
        self.assertFalse(SyntheticQuarantineBatch.objects.filter(pk=m["batch_id"]).exists())
        self.assertFalse(AuditEvent.objects.filter(correlation_id=m["batch_id"]).exists())

    def test_immutable_registered_manifest_cannot_be_rewritten(self):
        from django.core.exceptions import ValidationError
        from apps.core.models import SyntheticQuarantineBatch
        m = self.manifest()
        with self.assertRaises(ValidationError):
            SyntheticQuarantineBatch.objects.filter(pk=m["batch_id"]).update(
                manifest_sha256="0" * 64
            )
        batch = SyntheticQuarantineBatch.objects.get(pk=m["batch_id"])
        batch.manifest = {**m, "reason_code": "ATTACK"}
        with self.assertRaises(ValidationError):
            batch.save()
        self.assertEqual(
            SyntheticQuarantineBatch.objects.get(pk=m["batch_id"]).manifest,
            m,
        )

    def test_trusted_key_revocation_blocks_apply(self):
        from apps.core.models import SyntheticQuarantineBatch
        m = self.manifest()
        with override_settings(VORNEQ_QUARANTINE_OWNER_TRUST_ANCHORS={}):
            with self.assertRaisesRegex(QuarantineRejected, "ANCHOR_MISSING"):
                apply_quarantine(manifest=m, actor=self.owner)
        self.assertEqual(SyntheticQuarantineBatch.objects.get(pk=m["batch_id"]).state, "registered")
        self.assertTrue(self.article.is_published)

    def test_replay_of_registered_batch_rejected(self):
        from django.db import transaction, IntegrityError
        from apps.core.models import SyntheticQuarantineBatch
        m = self.manifest()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                register_signed_batch(
                    manifest=m, actor=self.owner,
                    signature_hex=self.owner_private_key.sign(signing_bytes(m)).hex(),
                    signing_key_id="local-simulated-owner",
                )
        self.assertEqual(SyntheticQuarantineBatch.objects.filter(pk=m["batch_id"]).count(), 1)

    def test_direct_bulk_batch_state_update_is_rejected(self):
        from django.core.exceptions import ValidationError
        from apps.core.models import SyntheticQuarantineBatch
        m = self.manifest()
        with self.assertRaisesRegex(ValidationError, "Bulk state"):
            SyntheticQuarantineBatch.objects.filter(pk=m["batch_id"]).update(state="held")
        batch = SyntheticQuarantineBatch.objects.get(pk=m["batch_id"])
        self.assertEqual(batch.state, "registered")

    def test_fresh_model_instance_cannot_overwrite_registered_uuid(self):
        from django.db import IntegrityError, transaction
        from apps.core.models import SyntheticQuarantineBatch
        m = self.manifest()
        saved = SyntheticQuarantineBatch.objects.get(pk=m["batch_id"])
        duplicate = SyntheticQuarantineBatch(
            batch_id=saved.batch_id,
            manifest=saved.manifest,
            manifest_sha256=saved.manifest_sha256,
            signature_hex=saved.signature_hex,
            signing_key_id=saved.signing_key_id,
            signer_fingerprint=saved.signer_fingerprint,
            authorization_reference=saved.authorization_reference,
            owner_account=saved.owner_account,
            state="held",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                duplicate.save()
        saved.refresh_from_db()
        self.assertEqual(saved.state, "registered")

# CI-only identity rules: unit tests do not connect to any real database.
class CiEphemeralPostgresIdentityGuardTests(__import__("django.test", fromlist=["SimpleTestCase"]).SimpleTestCase):
    def _fake_connection(self, *, host="postgres", user="vorneq",
                         name="test_vorneq", address="172.18.0.2",
                         actual_user="vorneq", port=5432):
        from unittest.mock import MagicMock
        conn = MagicMock()
        conn.settings_dict = {
            "HOST": host, "USER": user, "NAME": name, "PORT": "5432"
        }
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            actual_user, address, port
        )
        return conn

    def test_exact_ci_disposable_database_allowed_with_scoped_marker(self):
        from apps.core.synthetic_quarantine import _ci_ephemeral_postgres_test_identity
        with patch.dict(os.environ, {
            "VORNEQ_QUARANTINE_CI_DB_TEST_MODE": "DISPOSABLE_DJANGO_TEST_ONLY"
        }):
            self.assertEqual(
                _ci_ephemeral_postgres_test_identity(
                    self._fake_connection(), "test_vorneq"
                ), "test_vorneq"
            )

    def test_ci_disposable_database_requires_scoped_marker(self):
        from apps.core.synthetic_quarantine import _ci_ephemeral_postgres_test_identity
        with patch.dict(os.environ, {
            "VORNEQ_QUARANTINE_CI_DB_TEST_MODE": ""
        }):
            with self.assertRaisesRegex(QuarantineRejected, "EXPLICIT_OPT_IN"):
                _ci_ephemeral_postgres_test_identity(
                    self._fake_connection(), "test_vorneq"
                )

    def test_ci_guard_rejects_production_database_name(self):
        from apps.core.synthetic_quarantine import _ci_ephemeral_postgres_test_identity
        with patch.dict(os.environ, {
            "VORNEQ_QUARANTINE_CI_DB_TEST_MODE": "DISPOSABLE_DJANGO_TEST_ONLY"
        }):
            with self.assertRaisesRegex(QuarantineRejected, "ISOLATED_CLONE"):
                _ci_ephemeral_postgres_test_identity(
                    self._fake_connection(name="vorneq_production_db"),
                    "vorneq_production_db",
                )

    def test_ci_guard_rejects_noninternal_or_wrong_host(self):
        from apps.core.synthetic_quarantine import _ci_ephemeral_postgres_test_identity
        with patch.dict(os.environ, {
            "VORNEQ_QUARANTINE_CI_DB_TEST_MODE": "DISPOSABLE_DJANGO_TEST_ONLY"
        }):
            with self.assertRaisesRegex(QuarantineRejected, "TARGET_CONFIGURATION"):
                _ci_ephemeral_postgres_test_identity(
                    self._fake_connection(host="production-db.example.invalid"),
                    "test_vorneq",
                )
            with self.assertRaisesRegex(QuarantineRejected, "NETWORK_IDENTITY"):
                _ci_ephemeral_postgres_test_identity(
                    self._fake_connection(address="8.8.8.8"),
                    "test_vorneq",
                )

    def test_ci_guard_rejects_wrong_postgres_role(self):
        from apps.core.synthetic_quarantine import _ci_ephemeral_postgres_test_identity
        with patch.dict(os.environ, {
            "VORNEQ_QUARANTINE_CI_DB_TEST_MODE": "DISPOSABLE_DJANGO_TEST_ONLY"
        }):
            with self.assertRaisesRegex(QuarantineRejected, "NETWORK_IDENTITY"):
                _ci_ephemeral_postgres_test_identity(
                    self._fake_connection(actual_user="postgres"), "test_vorneq"
                )
