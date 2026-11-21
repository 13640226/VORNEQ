"""Deterministic Persian prose normalization, never applied to evidence.

This function accepts already-screened answer headings/text only. Quotes,
source excerpts, digests, IDs, URLs, and numeric tokens stay untouched.
"""
from __future__ import annotations

import re

_ARABIC = str.maketrans({"ي": "ی", "ك": "ک"})
_PROTECTED = re.compile(
    r"^[ \t]*\x60{3}[^\n]*\n[\s\S]*?(?:^[ \t]*\x60{3}[ \t]*(?:\n|$)|\Z)"
    r"|\x60[^\x60\n]+\x60|(?:https?://|www\.)[^\s<>]+",
    re.IGNORECASE | re.MULTILINE,
)
_PREFIX = re.compile(r"(?<![\w\u200c])((?:ن)?می)[ \t]+(?=[آ-ی][آ-ی])")
_SUFFIX = re.compile(r"(?<=[آ-ی])[ \t]+(هایی|های|ها|ترین|تر|دان)(?![\w\u200c])")


def _text(fragment: str) -> str:
    fragment = fragment.translate(_ARABIC)
    fragment = _PREFIX.sub(lambda m: m.group(1) + "\u200c", fragment)
    return _SUFFIX.sub(lambda m: "\u200c" + m.group(1), fragment)


def prose(text: str) -> str:
    """Normalize only prose spans; preserve URLs and Markdown code spans."""
    if not isinstance(text, str):
        raise TypeError("Persian prose must be text")
    segments = []
    last = 0
    for match in _PROTECTED.finditer(text):
        segments.extend((_text(text[last:match.start()]), match.group(0)))
        last = match.end()
    segments.append(_text(text[last:]))
    return "".join(segments)
