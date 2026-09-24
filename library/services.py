from apps.verification.public import get_public_verification_summary


def build_public_trust_context_for_library(library_item):
    """Return public-safe discovery context for one LibraryItem.

    This mirrors the Marketplace discovery contract while remaining
    descriptive only. It deliberately excludes reputation scores, verifier
    identities, private evidence, and any composite trust judgment.
    """
    summary = get_public_verification_summary(library_item)

    return {
        "has_verification": summary["total_verifications"] > 0,
        "verification_count": summary["total_verifications"],
        "verification_methods": summary.get("verification_methods", []),
        "public_evidence_count": summary["public_evidence_count"],
        "last_verified_at": summary.get("last_verified_at"),
    }
