"""Local-only, fail-closed proof of reversible synthetic-data quarantine.

NOT a production migration/command/entry point. Explicit IDs plus a pinned
manifest are required; no slug-only bulk update, no deletes, no external I/O.
"""
import hashlib
import json
import os
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connections, transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.content.models import Article
from apps.media.models import MediaAsset
from library.models import LibraryItem
from marketplace.models import Product


class QuarantineRejected(RuntimeError):
    pass


BASE_SHA = "4e748e9005c70dac926329c115c0ef06653fc01c"
BACKUP_SHA = "7434FFDC6434D15E2074D25FB4F64FC165AFADDC251299E33E9B8E8751A52304"
LOCAL_DB_NAME = "vorneq_quarantine_lab_20261113"
FLAG_FIELD = {
    "article": (Article, "is_published"),
    "product": (Product, "is_published"),
    "library": (LibraryItem, "is_published"),
    "media": (MediaAsset, "is_active"),
}
KINDS = tuple(FLAG_FIELD)
AUDIT_META = ("batch_id", "manifest_sha256", "row_count", "authorization_reference")


def _digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _date(value):
    return value.isoformat() if value else None


def _identity(using):
    if using != "default":
        raise QuarantineRejected("STOP_NONDEFAULT_ALIAS_UNSUPPORTED")
    if getattr(settings, "VORNEQ_ENV", None) != "development":
        raise QuarantineRejected("STOP_ENVIRONMENT_NOT_DEVELOPMENT")
    if os.environ.get("VORNEQ_QUARANTINE_LOCAL_ONLY") != "EXPLICIT_LOCAL_TEST":
        raise QuarantineRejected("STOP_LOCAL_OPT_IN_REQUIRED")
    if os.environ.get("DATABASE_URL"):
        raise QuarantineRejected("STOP_DATABASE_URL_PRESENT")
    conn = connections[using]
    if conn.vendor == "sqlite":
        name = str(conn.settings_dict["NAME"])
        if not (
            name == ":memory:" or "memorydb_" in name or name.startswith("test_")
        ):
            raise QuarantineRejected("STOP_SQLITE_NOT_TEST_DB")
        return "sqlite-test-lab"
    if conn.vendor == "postgresql":
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            actual = cursor.fetchone()[0]
        if actual not in {LOCAL_DB_NAME, "test_vorneq_signed_lab_20261113"}:
            raise QuarantineRejected("STOP_POSTGRES_NOT_ISOLATED_CLONE")
        return actual
    raise QuarantineRejected("STOP_UNSUPPORTED_DATABASE_BACKEND")


def _actor(actor):
    if not (
        getattr(actor, "is_authenticated", False)
        and getattr(actor, "is_active", False)
        and getattr(actor, "is_superuser", False)
        and getattr(actor, "pk", None) is not None
    ):
        raise PermissionDenied("Active authenticated superuser required.")


def _provenance(kind, obj):
    """Multiple observed seed markers; never rely on a slug alone."""
    if kind == "article":
        return (
            obj.slug.startswith("vorneq-benchmark-article-")
            and obj.editorial_metadata.get("benchmark_seed") is True
            and obj.category.slug == "vorneq-benchmark-category"
        )
    if kind == "product":
        if obj.slug == "inspect-staging-smoke":
            return obj.seller.username == "vorneq-inspect-smoke"
        return (
            obj.slug.startswith("vorneq-benchmark-product-")
            and obj.seller.username == "vorneq-benchmark-seed"
        )
    if kind == "library":
        return (
            obj.slug.startswith("vorneq-benchmark-library-")
            and obj.author == "VORNEQ Benchmark Seed"
            and obj.category == "benchmark"
        )
    if kind == "media":
        return (
            obj.title.startswith("VORNEQ Benchmark Media")
            and obj.presentation_metadata.get("benchmark_seed") is True
            and obj.file.name.startswith("benchmark/vorneq-benchmark-media-")
        )
    return False


def _snapshot(kind, obj):
    field = FLAG_FIELD[kind][1]
    return {
        "kind": kind,
        "object_id": str(obj.pk),
        "original_flag": getattr(obj, field),
        "original_status": obj.status if kind == "product" else None,
        "original_published_at": (
            _date(obj.published_at) if kind != "media" else None
        ),
        "original_updated_at": _date(obj.updated_at),
    }


def _lock_manifest_rows(manifest, *, using):
    result = []
    for kind in KINDS:
        source = [r for r in manifest["rows"] if r["kind"] == kind]
        if not source:
            continue
        model = FLAG_FIELD[kind][0]
        ids = [row["object_id"] for row in source]
        qs = model.objects.using(using).filter(pk__in=ids).order_by("pk").select_for_update()
        if kind == "article":
            qs = qs.select_related("category")
        if kind == "product":
            qs = qs.select_related("seller")
        objects = {str(obj.pk): obj for obj in qs}
        if len(objects) != len(ids):
            raise QuarantineRejected("STOP_MISSING_ROW")
        for row in source:
            obj = objects.get(row["object_id"])
            if obj is None or not _provenance(kind, obj):
                raise QuarantineRejected("STOP_PROVENANCE_MISMATCH")
            result.append((row, obj))
    if len(result) != len(manifest["rows"]):
        raise QuarantineRejected("STOP_MANIFEST_ROW_COUNT_MISMATCH")
    return result


def _validate_manifest(manifest, actor, *, using):
    _actor(actor)
    ident = _identity(using)
    if not isinstance(manifest, dict):
        raise QuarantineRejected("STOP_MANIFEST_TYPE")
    expected = {
        "schema_version", "batch_id", "source_database_identity",
        "backup_sha256", "repository_base_sha", "authorized_actor",
        "authorization_reference", "reason_code", "counts", "rows",
        "manifest_sha256",
    }
    if set(manifest) != expected:
        raise QuarantineRejected("STOP_MANIFEST_SCHEMA")
    signature = manifest["manifest_sha256"]
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if signature != _digest(body):
        raise QuarantineRejected("STOP_MANIFEST_DIGEST")
    if (
        manifest["schema_version"] != 1
        or manifest["source_database_identity"] != ident
        or manifest["repository_base_sha"] != BASE_SHA
        or manifest["backup_sha256"] != BACKUP_SHA
        or str(actor.pk) != manifest["authorized_actor"]
        or not manifest["authorization_reference"]
        or manifest["reason_code"] != "SYNTHETIC_QUARANTINE"
    ):
        raise QuarantineRejected("STOP_SCOPE_OR_AUTHORITY_MISMATCH")
    try:
        uuid.UUID(manifest["batch_id"])
    except (TypeError, ValueError, AttributeError) as exc:
        raise QuarantineRejected("STOP_BATCH_ID_INVALID") from exc
    rows = manifest["rows"]
    if not isinstance(rows, list) or not rows:
        raise QuarantineRejected("STOP_EMPTY_ROWS")
    pairs = [(r["kind"], r["object_id"]) for r in rows]
    if len(set(pairs)) != len(pairs):
        raise QuarantineRejected("STOP_DUPLICATE_MANIFEST_ID")
    if any(k not in KINDS for k, _ in pairs):
        raise QuarantineRejected("STOP_UNKNOWN_KIND")
    if any(r["original_flag"] is not True for r in rows):
        raise QuarantineRejected("STOP_NONPUBLIC_ROW_IN_MANIFEST")
    counts = {kind: sum(r["kind"] == kind for r in rows) for kind in KINDS}
    if counts != manifest["counts"]:
        raise QuarantineRejected("STOP_EXPECTED_COUNTS_MISMATCH")


def prepare_manifest(
    *, ids_by_kind, actor, batch_id, authorization_reference,
    backup_sha256=BACKUP_SHA, repository_base_sha=BASE_SHA, using="default",
):
    """Read-only. Call with explicit, independently vetted IDs only."""
    _actor(actor)
    ident = _identity(using)
    rows = []
    for kind in KINDS:
        ids = [str(value) for value in ids_by_kind.get(kind, ())]
        if len(set(ids)) != len(ids):
            raise QuarantineRejected("STOP_DUPLICATE_IDS")
        model, flag = FLAG_FIELD[kind]
        qs = model.objects.using(using).filter(pk__in=ids).order_by("pk")
        if kind == "article":
            qs = qs.select_related("category")
        if kind == "product":
            qs = qs.select_related("seller")
        objs = list(qs)
        if len(objs) != len(ids):
            raise QuarantineRejected("STOP_PREPARE_MISSING_ROW")
        for obj in objs:
            if not _provenance(kind, obj) or not getattr(obj, flag):
                raise QuarantineRejected("STOP_PREPARE_PROVENANCE_OR_FLAG")
            rows.append(_snapshot(kind, obj))
    if not rows:
        raise QuarantineRejected("STOP_EMPTY_MANIFEST")
    counts = {kind: sum(r["kind"] == kind for r in rows) for kind in KINDS}
    body = {
        "schema_version": 1,
        "batch_id": str(batch_id),
        "source_database_identity": ident,
        "backup_sha256": backup_sha256,
        "repository_base_sha": repository_base_sha,
        "authorized_actor": str(actor.pk),
        "authorization_reference": authorization_reference,
        "reason_code": "SYNTHETIC_QUARANTINE",
        "counts": counts,
        "rows": rows,
    }
    result = dict(body)
    result["manifest_sha256"] = _digest(body)
    _validate_manifest(result, actor, using=using)
    return result


def _audit(event_suffix, manifest, actor, *, using):
    metadata = {
        "batch_id": manifest["batch_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "row_count": len(manifest["rows"]),
        "authorization_reference": manifest["authorization_reference"],
    }
    is_rollback = event_suffix.startswith("revert")
    reason = "SYNTHETIC_REVERT" if is_rollback else "SYNTHETIC_QUARANTINE"
    return record_audit_event(
        event_name="synthetic.quarantine." + event_suffix,
        actor={"type": "user", "identifier": actor.pk},
        target={"type": "QuarantineBatch", "identifier": manifest["batch_id"]},
        outcome=(
            AuditEvent.Outcome.SUCCEEDED if event_suffix.endswith("verified")
            else AuditEvent.Outcome.CHANGED
        ),
        metadata=metadata,
        reason_code=reason,
        correlation_id=manifest["batch_id"],
        retention_class=AuditEvent.RetentionClass.SECURITY,
    )


def _has_event(manifest, event, *, using):
    return AuditEvent.objects.using(using).filter(
        correlation_id=manifest["batch_id"],
        event_name="synthetic.quarantine." + event,
    ).exists()


def _check_rows(locked, *, phase):
    for row, obj in locked:
        actual = _snapshot(row["kind"], obj)
        for key in ("original_status", "original_published_at", "original_updated_at"):
            if actual[key] != row[key]:
                raise QuarantineRejected("STOP_NONFLAG_FIELD_CHANGED")
        flag = actual["original_flag"]
        expected_flag = True if phase == "apply" else False
        if flag is not expected_flag:
            raise QuarantineRejected("STOP_VISIBILITY_STATE_CHANGED")


def _write_flags(locked, value, *, using):
    changed = 0
    for row, _obj in locked:
        model, field = FLAG_FIELD[row["kind"]]
        n = model.objects.using(using).filter(pk=row["object_id"]).update(**{field: value})
        if n != 1:
            raise QuarantineRejected("STOP_NONATOMIC_ROW_COUNT")
        changed += n
    return changed


def apply_quarantine(*, manifest, actor, using="default"):
    """Local-only all-or-nothing transition with atomic audit events."""
    _validate_manifest(manifest, actor, using=using)
    with transaction.atomic(using=using):
        batch = _locked_signed_batch(
            manifest, actor, using=using, required_state="registered"
        )
        locked = _lock_manifest_rows(manifest, using=using)
        if _has_event(manifest, "applied", using=using):
            raise QuarantineRejected("STOP_BATCH_ALREADY_APPLIED")
        _check_rows(locked, phase="apply")
        _audit("requested", manifest, actor, using=using)
        _audit("precheck_passed", manifest, actor, using=using)
        _write_flags(locked, False, using=using)
        for row, _ in locked:
            model, field = FLAG_FIELD[row["kind"]]
            if model.objects.using(using).filter(pk=row["object_id"], **{field: True}).exists():
                raise QuarantineRejected("STOP_POST_APPLY_VISIBILITY")
        _audit("applied", manifest, actor, using=using)
        _audit("verified", manifest, actor, using=using)
        batch.state = "held"
        batch.held_at = timezone.now()
        batch.save(update_fields=["state", "held_at"], using=using)
    return len(locked)


def revert_quarantine(*, manifest, actor, using="default"):
    """Restore only previously held flags; preserve status and timestamps."""
    _validate_manifest(manifest, actor, using=using)
    with transaction.atomic(using=using):
        batch = _locked_signed_batch(
            manifest, actor, using=using, required_state="held"
        )
        locked = _lock_manifest_rows(manifest, using=using)
        if not _has_event(manifest, "applied", using=using):
            raise QuarantineRejected("STOP_NO_PREVIOUS_APPLY_EVENT")
        if _has_event(manifest, "reverted", using=using):
            raise QuarantineRejected("STOP_BATCH_ALREADY_REVERTED")
        _check_rows(locked, phase="revert")
        _audit("revert_requested", manifest, actor, using=using)
        _write_flags(locked, True, using=using)
        for row, _ in locked:
            model, field = FLAG_FIELD[row["kind"]]
            if not model.objects.using(using).filter(pk=row["object_id"], **{field: True}).exists():
                raise QuarantineRejected("STOP_POST_REVERT_STATE")
        _audit("reverted", manifest, actor, using=using)
        _audit("revert_verified", manifest, actor, using=using)
        batch.state = "reverted"
        batch.reverted_at = timezone.now()
        batch.save(update_fields=["state", "reverted_at"], using=using)
    return len(locked)

# Signed manifest authorization and persistence contract, LOCAL LAB ONLY.
# A public key is NEVER inferred from the manifest or from a user-supplied
# signature envelope. It must be pinned in Django trusted configuration
# before any manifest is accepted.
OWNER_ACCOUNT = "13640226"
SIGNING_DOMAIN = b"VORNEQ_QUARANTINE_MANIFEST_V1\\n"


def signing_bytes(manifest):
    if not isinstance(manifest, dict):
        raise QuarantineRejected("STOP_INVALID_SIGNING_INPUT")
    return SIGNING_DOMAIN + json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _trusted_signature(manifest, signature_hex, signing_key_id):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    anchors = getattr(settings, "VORNEQ_QUARANTINE_OWNER_TRUST_ANCHORS", {})
    if not isinstance(anchors, dict):
        raise QuarantineRejected("STOP_TRUST_CONFIGURATION_INVALID")
    anchor = anchors.get(signing_key_id)
    if not isinstance(anchor, dict):
        raise QuarantineRejected("STOP_OWNER_TRUST_ANCHOR_MISSING")
    if (
        anchor.get("status") != "preapproved"
        or anchor.get("owner_account") != OWNER_ACCOUNT
        or anchor.get("authorization_reference") != manifest.get("authorization_reference")
    ):
        raise QuarantineRejected("STOP_OWNER_KEY_NOT_PREAPPROVED")
    try:
        public_key_bytes = bytes.fromhex(anchor["public_key_ed25519_hex"])
        signature = bytes.fromhex(signature_hex)
        fingerprint = hashlib.sha256(public_key_bytes).hexdigest()
        if (
            len(public_key_bytes) != 32
            or len(signature) != 64
            or anchor.get("fingerprint_sha256") != fingerprint
        ):
            raise QuarantineRejected("STOP_OWNER_KEY_FINGERPRINT_MISMATCH")
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
            signature, signing_bytes(manifest)
        )
    except (ValueError, TypeError, KeyError, InvalidSignature) as exc:
        raise QuarantineRejected("STOP_INVALID_OWNER_SIGNATURE") from exc
    return fingerprint


def register_signed_batch(
    *, manifest, actor, signature_hex, signing_key_id, using="default"
):
    """Commit a signed manifest and one audit event in the SAME DB transaction.

    Only a separately pinned, preapproved owner public key is accepted.
    This prototype cannot auto-enroll keys or issue owner approval.
    """
    from apps.core.models import SyntheticQuarantineBatch

    _validate_manifest(manifest, actor, using=using)
    fingerprint = _trusted_signature(manifest, signature_hex, signing_key_id)
    with transaction.atomic(using=using):
        locked = _lock_manifest_rows(manifest, using=using)
        _check_rows(locked, phase="apply")
        batch = SyntheticQuarantineBatch(
            batch_id=uuid.UUID(manifest["batch_id"]),
            manifest=manifest,
            manifest_sha256=manifest["manifest_sha256"],
            signature_hex=signature_hex,
            signing_key_id=signing_key_id,
            signer_fingerprint=fingerprint,
            authorization_reference=manifest["authorization_reference"],
            owner_account=OWNER_ACCOUNT,
        )
        batch.save(force_insert=True, using=using)
        _audit("registered", manifest, actor, using=using)
    return batch


def _locked_signed_batch(manifest, actor, *, using, required_state):
    from apps.core.models import SyntheticQuarantineBatch

    batch = (
        SyntheticQuarantineBatch.objects.using(using)
        .select_for_update()
        .get(pk=uuid.UUID(manifest["batch_id"]))
    )
    if batch.manifest != manifest or batch.manifest_sha256 != manifest["manifest_sha256"]:
        raise QuarantineRejected("STOP_PERSISTED_MANIFEST_CHANGED")
    if (
        batch.owner_account != OWNER_ACCOUNT
        or batch.authorization_reference != manifest["authorization_reference"]
        or batch.state != required_state
    ):
        raise QuarantineRejected("STOP_PERSISTED_STATE_OR_AUTHORITY")
    fingerprint = _trusted_signature(
        batch.manifest, batch.signature_hex, batch.signing_key_id
    )
    if fingerprint != batch.signer_fingerprint:
        raise QuarantineRejected("STOP_PERSISTED_SIGNING_KEY_CHANGED")
    if not _has_event(manifest, "registered", using=using):
        raise QuarantineRejected("STOP_MISSING_REGISTRATION_AUDIT")
    return batch
