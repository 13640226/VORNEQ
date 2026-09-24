import base64
import hashlib
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from django.db import transaction

from apps.evidence.models import Evidence, ProvenanceStep, SignatureEnvelope
from apps.verification.models import VerificationResult


CANONICAL_VERSION = "trust-signature-v1"


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    raise TypeError(f"Unsupported datetime value: {type(value)!r}")


def canonical_payload(target) -> dict:
    """Return the versioned canonical payload for a supported trust object."""
    if isinstance(target, Evidence):
        return {
            "canonical_version": CANONICAL_VERSION,
            "type": "evidence",
            "id": str(target.pk),
            "content": target.content,
            "content_type": target.content_type,
            "observed_at": _iso(target.observed_at),
            "integrity_digest": target.integrity_digest,
            "created_by_id": target.created_by_id,
            "created_at": _iso(target.created_at),
        }
    if isinstance(target, ProvenanceStep):
        return {
            "canonical_version": CANONICAL_VERSION,
            "type": "provenance_step",
            "id": str(target.pk),
            "evidence_id": str(target.evidence_id),
            "source_type": target.source_type,
            "source_ref": target.source_ref,
            "transformation": target.transformation,
            "timestamp": _iso(target.timestamp),
            "note": target.note,
        }
    if isinstance(target, VerificationResult):
        return {
            "canonical_version": CANONICAL_VERSION,
            "type": "verification_result",
            "id": str(target.pk),
            "request_id": target.request_id,
            "verifier_id": target.verifier_id,
            "outcome": target.outcome,
            "reported_confidence": target.reported_confidence,
            "summary": target.summary,
            "metadata": target.metadata,
            "created_at": _iso(target.created_at),
        }
    raise TypeError(f"Unsupported signature target: {type(target)!r}")


def canonical_bytes(target) -> bytes:
    if getattr(target, "_state", None) is None or target._state.adding:
        raise ValueError("Signature target must be persisted before signing.")
    return json.dumps(
        canonical_payload(target),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def payload_digest(target) -> str:
    return hashlib.sha256(canonical_bytes(target)).hexdigest()


def _load_private_key(private_key_pem: str | bytes) -> Ed25519PrivateKey:
    if isinstance(private_key_pem, str):
        private_key_pem = private_key_pem.encode("utf-8")
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Signing key must be an Ed25519 private key.")
    return key


def _load_public_key(public_key_pem: str | bytes) -> Ed25519PublicKey:
    if isinstance(public_key_pem, str):
        public_key_pem = public_key_pem.encode("utf-8")
    key = serialization.load_pem_public_key(public_key_pem)
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Verification key must be an Ed25519 public key.")
    return key


def get_public_key(private_key_pem: str | bytes) -> str:
    key = _load_private_key(private_key_pem)
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


@transaction.atomic
def sign_object(*, target, private_key_pem: str | bytes, key_id: str) -> SignatureEnvelope:
    if not isinstance(key_id, str) or not key_id.strip():
        raise ValueError("key_id is required.")

    serialized = canonical_bytes(target)
    digest = hashlib.sha256(serialized).hexdigest()
    signature = _load_private_key(private_key_pem).sign(serialized)

    kwargs = {
        "key_id": key_id.strip(),
        "algorithm": SignatureEnvelope.Algorithm.ED25519,
        "canonical_version": CANONICAL_VERSION,
        "payload_digest": digest,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    if isinstance(target, Evidence):
        kwargs["evidence"] = target
    elif isinstance(target, ProvenanceStep):
        kwargs["provenance_step"] = target
    elif isinstance(target, VerificationResult):
        kwargs["verification_result"] = target
    else:
        raise TypeError(f"Unsupported signature target: {type(target)!r}")

    envelope = SignatureEnvelope(**kwargs)
    envelope.full_clean()
    envelope.save()
    return envelope


def verify_signature(*, envelope: SignatureEnvelope, public_key_pem: str | bytes) -> bool:
    target = envelope.target
    if target is None or envelope.algorithm != SignatureEnvelope.Algorithm.ED25519:
        return False

    serialized = canonical_bytes(target)
    digest = hashlib.sha256(serialized).hexdigest()
    if digest != envelope.payload_digest:
        return False

    try:
        signature = base64.b64decode(envelope.signature, validate=True)
        _load_public_key(public_key_pem).verify(signature, serialized)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
