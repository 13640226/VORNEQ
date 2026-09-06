from apps.verification.public import get_public_verification_summary


def build_public_trust_context(product):
    """Return public-safe discovery context for one marketplace product.

    This is descriptive only. It deliberately excludes reputation scores,
    verifier identities, private evidence, and any composite trust judgment.
    """
    summary = get_public_verification_summary(product)

    return {
        "has_verification": summary["total_verifications"] > 0,
        "verification_count": summary["total_verifications"],
        "verification_methods": summary.get("verification_methods", []),
        "public_evidence_count": summary["public_evidence_count"],
        "last_verified_at": summary.get("last_verified_at"),
    }
