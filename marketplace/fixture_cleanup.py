"""Strict, audited one-time removal of known Marketplace seed fixtures.

Not an automatic migration. The command defaults to read-only. Production
execution requires separately configured release-bound gates, a verified backup,
a precisely pinned product ID set and a database transaction with audit events.
"""
import hashlib
import os

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.contrib.contenttypes.models import ContentType

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.core.models import Artifact, ArtifactBinding, Entitlement
from marketplace.models import Product, ProductReview


class FixtureCleanupRejected(RuntimeError):
    """Refuse to mutate anything when the scope or authority is uncertain."""


SERVICE_ID = "srv-dadn07eq1p3s73eccau0"
DATABASE_NAME = "vorneq_production_db"
EXPECTED_COUNT = 501
EXPECTED_IDS_DIGEST = "8fb10e4590fb421a8270a1f85d74904f51e23186f8da76f5a8194d2ec2bdba7b"
BACKUP_DIGEST = "16bf832ba27a68065322b80ea3f97bde5781e526afbd8b07211e9c2098070dec"
BACKUP_EVIDENCE_ID = "VQ_MARKETPLACE_PG18_FULL_BACKUP_20261119_0016Z"
BATCH_ID = "VQ-MARKETPLACE-FIXTURE-DELETE-501-20261119-OWNER01"
OWNER_REFERENCE = "OWNER_13640226_20261119_DELETE_MARKETPLACE_FIXTURES"


def _strict_fixture(product):
    """Two independent observed identity signals, not a slug-only selection."""
    return (
        product.slug.startswith("vorneq-benchmark-product-")
        and product.seller.username == "vorneq-benchmark-seed"
    ) or (
        product.slug == "inspect-staging-smoke"
        and product.seller.username == "vorneq-inspect-smoke"
    )


def _hash_ids(rows):
    return hashlib.sha256(
        ",".join(str(item.pk) for item in rows).encode("ascii")
    ).hexdigest()


def _check_context(*, apply, local_test):
    """Default-deny: independent runtime authorization is required to write."""
    if local_test:
        name = str(connection.settings_dict.get("NAME", ""))
        if not (
            getattr(settings, "VORNEQ_ENV", "") == "development"
            and os.environ.get("VORNEQ_FIXTURE_CLEANUP_LOCAL_TEST") == "EXPLICIT_TEST_ONLY"
            and (name == ":memory:" or "memorydb_" in name or name.startswith("test_"))
        ):
            raise FixtureCleanupRejected("STOP_LOCAL_TEST_ISOLATION")
        return
    if getattr(settings, "VORNEQ_ENV", "") != "production":
        raise FixtureCleanupRejected("STOP_PRODUCTION_ENV_IDENTITY")
    if connection.vendor != "postgresql":
        raise FixtureCleanupRejected("STOP_BACKEND_IDENTITY")
    if os.environ.get("RENDER_SERVICE_ID") != SERVICE_ID:
        raise FixtureCleanupRejected("STOP_SERVICE_IDENTITY")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != DATABASE_NAME:
            raise FixtureCleanupRejected("STOP_DATABASE_IDENTITY")
    if apply:
        sha = os.environ.get("RENDER_GIT_COMMIT", "")
        if not (len(sha) == 40 and all(char in "0123456789abcdef" for char in sha)):
            raise FixtureCleanupRejected("STOP_GIT_SHA_MISSING")
        gates = {
            "VORNEQ_MARKETPLACE_CLEANUP_EXECUTION": "OWNER_APPROVED_ONE_TIME_501",
            "VORNEQ_MARKETPLACE_CLEANUP_AUTHORIZED_SHA": sha,
            "VORNEQ_MARKETPLACE_CLEANUP_BACKUP_SHA256": BACKUP_DIGEST,
            "VORNEQ_MARKETPLACE_CLEANUP_RESTORE_EVIDENCE": BACKUP_EVIDENCE_ID,
            "VORNEQ_MARKETPLACE_CLEANUP_OWNER_REFERENCE": OWNER_REFERENCE,
        }
        if not all(os.environ.get(k) == v for k, v in gates.items()):
            raise FixtureCleanupRejected("STOP_MISSING_INDEPENDENT_EXECUTION_AUTHORITY")


def _verify_dependents(ids, *, local_test):
    """Reject any direct FK or generic relation not explicitly accounted for."""
    if Entitlement.objects.filter(product_id__in=ids).exists():
        raise FixtureCleanupRejected("STOP_ENTITLEMENT_REFERENCE")
    if ProductReview.objects.filter(product_id__in=ids).exists():
        raise FixtureCleanupRejected("STOP_REVIEW_REFERENCE")
    if local_test:
        return
    # This catalog scan handles future FK-bearing models not known at author time.
    from psycopg2 import sql

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT ns.nspname, src.relname, att.attname
            FROM pg_constraint fk
            JOIN pg_class src ON src.oid = fk.conrelid
            JOIN pg_namespace ns ON ns.oid = src.relnamespace
            JOIN pg_attribute att ON att.attrelid = src.oid
                 AND att.attnum = fk.conkey[1]
            WHERE fk.contype = 'f'
              AND fk.confrelid = 'marketplace_product'::regclass
              AND cardinality(fk.conkey) = 1
        """)
        for schema, table, field in cursor.fetchall():
            statement = sql.SQL(
                "SELECT COUNT(*) FROM {}.{} WHERE {} = ANY(%s)"
            ).format(sql.Identifier(schema), sql.Identifier(table), sql.Identifier(field))
            cursor.execute(statement, (ids,))
            if cursor.fetchone()[0]:
                raise FixtureCleanupRejected("STOP_PRODUCT_FOREIGN_KEY_REFERENCE")
        cursor.execute("""
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = 'content_type_id'
            INTERSECT
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = 'object_id'
        """)
        tables = cursor.fetchall()
        cursor.execute("""
            SELECT id FROM django_content_type
            WHERE app_label = 'marketplace' AND model = 'product'
        """)
        ct_row = cursor.fetchone()
        if ct_row is None:
            raise FixtureCleanupRejected("STOP_CONTENT_TYPE_MISSING")
        ct_id = ct_row[0]
        id_texts = {str(pk) for pk in ids}
        for schema, table in tables:
            statement = sql.SQL(
                "SELECT object_id::text FROM {}.{} WHERE content_type_id = %s"
            ).format(sql.Identifier(schema), sql.Identifier(table))
            cursor.execute(statement, (ct_id,))
            hits = [value for (value,) in cursor.fetchall() if value in id_texts]
            if table == "core_artifactbinding":
                if hits != ["501"]:
                    raise FixtureCleanupRejected("STOP_GENERIC_BINDING_DRIFT")
            elif hits:
                raise FixtureCleanupRejected("STOP_UNEXPECTED_GENERIC_REFERENCE")


def _verify_artifact_dependencies(artifact, *, local_test):
    if local_test:
        return
    from psycopg2 import sql

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT ns.nspname, src.relname, att.attname
            FROM pg_constraint fk
            JOIN pg_class src ON src.oid = fk.conrelid
            JOIN pg_namespace ns ON ns.oid = src.relnamespace
            JOIN pg_attribute att ON att.attrelid = src.oid
                 AND att.attnum = fk.conkey[1]
            WHERE fk.contype = 'f'
              AND fk.confrelid = 'core_artifact'::regclass
              AND cardinality(fk.conkey) = 1
        """)
        for schema, table, field in cursor.fetchall():
            statement = sql.SQL(
                "SELECT COUNT(*) FROM {}.{} WHERE {} = %s"
            ).format(sql.Identifier(schema), sql.Identifier(table), sql.Identifier(field))
            cursor.execute(statement, (str(artifact.pk),))
            count = cursor.fetchone()[0]
            expected = 1 if table == "core_artifactbinding" else 0
            if count != expected:
                raise FixtureCleanupRejected("STOP_ARTIFACT_DEPENDENCY_DRIFT")


def cleanup(*, apply=False, local_test=False, expected_ids_digest=None):
    """Dry-run by default; apply is atomic and creates two append-only audit events.

    The local test route is exclusively for disposable Django test databases.
    """
    _check_context(apply=apply, local_test=local_test)
    with transaction.atomic():
        if apply and connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '3s'")
                cursor.execute("SET LOCAL statement_timeout = '20s'")
                cursor.execute("SELECT pg_try_advisory_xact_lock(20261119, 501)")
                if not cursor.fetchone()[0]:
                    raise FixtureCleanupRejected("STOP_CONCURRENT_CLEANUP")
        if not apply and connection.vendor == "postgresql" and not local_test:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
        products = list(Product.objects.select_related("seller").order_by("pk"))
        if apply:
            products = list(
                Product.objects.select_related("seller")
                .select_for_update().order_by("pk")
            )
        ids = [p.pk for p in products]
        expected_count = 2 if local_test else EXPECTED_COUNT
        expected_digest = expected_ids_digest if local_test else EXPECTED_IDS_DIGEST
        if len(products) != expected_count or _hash_ids(products) != expected_digest:
            raise FixtureCleanupRejected("STOP_EXPECTED_PRODUCT_SET_DRIFT")
        if not all(_strict_fixture(p) for p in products):
            raise FixtureCleanupRejected("STOP_FIXTURE_PROVENANCE_MISMATCH")
        if any(
            p.status != Product.STATUS_APPROVED
            or not p.is_published or p.published_at is None
            or p.image or p.digital_file
            for p in products
        ):
            raise FixtureCleanupRejected("STOP_PRODUCT_STATE_DRIFT")
        _verify_dependents(ids, local_test=local_test)
        ct = ContentType.objects.get(app_label="marketplace", model="product")
        bindings = list(
            ArtifactBinding.objects.select_related("artifact")
            .filter(content_type=ct, object_id=str(max(ids)))
        )
        if len(bindings) != 1:
            raise FixtureCleanupRejected("STOP_EXPECTED_ONE_ARTIFACT_BINDING")
        binding = bindings[0]
        if not local_test and (max(ids) != 501 or str(binding.object_id) != "501"):
            raise FixtureCleanupRejected("STOP_PRODUCT_501_BINDING")
        artifact = binding.artifact
        if artifact.kind != Artifact.Kind.PRODUCT or not artifact.is_active or artifact.metadata != {}:
            raise FixtureCleanupRejected("STOP_ARTIFACT_STATE_DRIFT")
        _verify_artifact_dependencies(artifact, local_test=local_test)

        result = {
            "candidate_count": len(products),
            "id_set_sha256": _hash_ids(products),
            "binding_count": len(bindings),
            "backup_sha256": BACKUP_DIGEST,
            "would_delete": not apply,
        }
        if not apply:
            return result

        event_meta = {
            "batch_id": BATCH_ID,
            "row_count": len(products),
            "id_set_sha256": result["id_set_sha256"],
            "backup_sha256": BACKUP_DIGEST,
            "authorization_reference": OWNER_REFERENCE,
            "artifact_binding_count": 1,
            "artifact_id": str(artifact.pk),
            "linked_product_id": max(ids),
            "runtime_sha": os.environ.get("RENDER_GIT_COMMIT", "LOCAL_TEST") if not local_test else "LOCAL_TEST",
        }
        if AuditEvent.objects.filter(correlation_id=BATCH_ID).exists():
            raise FixtureCleanupRejected("STOP_ALREADY_EXECUTED")
        audit_args = {
            "actor": {"type": "system", "identifier": "owner-approved-13640226"},
            "target": {"type": "MarketplaceFixtureBatch", "identifier": BATCH_ID},
            "metadata": event_meta,
            "reason_code": "OWNER_APPROVED_FIXTURE_CLEANUP",
            "correlation_id": BATCH_ID,
            "retention_class": AuditEvent.RetentionClass.SECURITY,
        }
        record_audit_event(
            event_name="marketplace.synthetic_cleanup.started",
            outcome=AuditEvent.Outcome.CHANGED,
            **audit_args,
        )
        deleted_bindings, _ = ArtifactBinding.objects.filter(pk=binding.pk).delete()
        if deleted_bindings != 1:
            raise FixtureCleanupRejected("STOP_BINDING_DELETE_FAILED")
        if Artifact.objects.filter(pk=artifact.pk, is_active=True).update(is_active=False) != 1:
            raise FixtureCleanupRejected("STOP_TOMBSTONE_FAILED")
        deleted, breakdown = Product.objects.filter(pk__in=ids).delete()
        if deleted != len(ids) or sum(breakdown.values()) != len(ids):
            raise FixtureCleanupRejected("STOP_UNEXPECTED_DELETE_CASCADE")
        if Product.objects.exists():
            raise FixtureCleanupRejected("STOP_PRODUCTS_REMAIN")
        if not Artifact.objects.filter(pk=artifact.pk, is_active=False).exists():
            raise FixtureCleanupRejected("STOP_TOMBSTONE_NOT_FOUND")
        record_audit_event(
            event_name="marketplace.synthetic_cleanup.completed",
            outcome=AuditEvent.Outcome.SUCCEEDED,
            **audit_args,
        )
        result["would_delete"] = False
        result["deleted"] = deleted
        result["tombstoned_artifacts"] = 1
        result["audited_events"] = 2
        return result
