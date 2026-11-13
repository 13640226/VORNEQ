"""Bounded, reviewed snapshots of public VORNEQ pages for grounded answers.

These are source *excerpts*, not claims of independent verification. Update the
snapshots only after checking the corresponding publicly rendered pages. Do
not fetch arbitrary URLs, accept user-supplied URLs, or read private content.
Observed on staging 2026-11-13; changes to live pages require re-review.
"""
from __future__ import annotations

import re

from apps.ai_core.gateway import Citation

_BRAND = re.compile(r"(?i)(?<![a-z0-9])vorneq(?![a-z0-9])")

# Explicit relative paths are served publicly by the localized Django site.
# Each excerpt is from the named public page, with no fabricated capability
# claims and no dated technical report treated as current operational truth.
_SOURCES = (
    ("official:home", "VORNEQ AI workspace",
     "Search, documents, notes and marketplace in one VORNEQ workspace. "
     "Sign in to create documents and notes and to share them with exactly the people you choose.",
     "/en/"),
    ("official:orientation", "VORNEQ evidence vocabulary",
     "A short guide to the terms used across Discover, Context, and the Evidence Graph. "
     "Evidence is recorded material connected to an artifact through a public evidence relationship. "
     "Provenance is recorded source and time context associated with public evidence.",
     "/en/orientation/"),
)


def retrieve_official_public(question: str, language: str) -> tuple[Citation, ...]:
    """Return reviewed public-page snapshots only for explicit platform queries.

    Source content is a bounded snapshot; the model must not treat it as
    live verification. Never expand arbitrary queries to this corpus.
    """
    if not isinstance(question, str) or not _BRAND.search(question):
        return ()
    return tuple(
        Citation("S" + str(i), key, title, excerpt, url)
        for i, (key, title, excerpt, url) in enumerate(_SOURCES, 1)
    )
