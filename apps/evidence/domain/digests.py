"""
Deterministic SHA-256 helpers for the Evidence domain.
"""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


DIGEST_VERSION = "v1"


def _json_default(value):
    """
    Convert supported Python values to deterministic
    JSON-compatible representations.
    """

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, Enum):
        return value.value

    raise TypeError(
        "Unsupported value for canonical digest: "
        f"{type(value).__name__}"
    )


def canonical_json(data) -> str:
    """
    Return deterministic canonical JSON.

    Rules:
    - keys sorted
    - no insignificant whitespace
    - Unicode preserved
    - deterministic handling of supported Python values
    """

    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def sha256_digest(data) -> str:
    """
    Return lowercase hexadecimal SHA-256 of canonical JSON.
    """

    encoded = canonical_json(data).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evidence_digest(
    *,
    content: str,
    content_type: str,
) -> str:
    """
    Compute the canonical Evidence integrity digest.

    metadata is deliberately excluded because it is mutable.

    observed_at is also excluded: integrity_digest represents
    canonical Evidence content and content type.
    """

    return sha256_digest(
        {
            "content": content,
            "content_type": content_type,
        }
    )


def snapshot_digest(
    *,
    claim_id,
    review_id,
    state: str,
    timestamp,
    digest_version: str = DIGEST_VERSION,
) -> str:
    """
    Compute deterministic, versioned AssessmentSnapshot digest.

    This follows ADR-001 v1.0 Frozen.
    """

    return sha256_digest(
        {
            "claim_id": str(claim_id),
            "review_id": str(review_id),
            "state": state,
            "timestamp": (
                timestamp.isoformat()
                if isinstance(timestamp, datetime)
                else str(timestamp)
            ),
            "digest_version": digest_version,
        }
    )