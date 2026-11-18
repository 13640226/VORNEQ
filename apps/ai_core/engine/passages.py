"""Bounded deterministic passages for V3 Stage 2 public evidence.

Passage text is an exact substring of the trusted, screened excerpt; it is
never a paraphrase. The original evidence digest always refers to the full
source excerpt, not to a model-generated text.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_ID = re.compile(r"S[1-5]\Z")
SPACE = re.compile(r"\s")
MAX_PASSAGES = 24
MAX_SOURCES = 5
MIN_CHARS = 80
MAX_CHARS = 300


@dataclass(frozen=True)
class Passage:
    passage_id: str
    source_id: str
    text: str
    start: int
    end: int


def split(sources) -> tuple[Passage, ...]:
    """Split screened sources into 80..300-char verbatim ranges.

    A last short fragment is merged with its preceding range when possible.
    Otherwise a fragment under 80 chars is omitted rather than misquoted.
    IDs are stable for identical source order and excerpt content.
    """
    if not isinstance(sources, (tuple, list)) or not 1 <= len(sources) <= MAX_SOURCES:
        raise ValueError("invalid source collection")
    out: list[Passage] = []
    for source in sources:
        if not isinstance(source, dict) or not _ID.fullmatch(str(source.get("source_id", ""))):
            raise ValueError("invalid source identity")
        sid = source["source_id"]
        excerpt = source.get("excerpt")
        if not isinstance(excerpt, str) or len(excerpt) > 1500:
            raise ValueError("invalid source excerpt")
        positions: list[tuple[int, int]] = []
        start = 0
        while start < len(excerpt):
            while start < len(excerpt) and excerpt[start].isspace():
                start += 1
            if start >= len(excerpt):
                break
            end = min(start + MAX_CHARS, len(excerpt))
            if end < len(excerpt):
                # Prefer the last natural separator in the latter half;
                # preserve the original characters and offset exactly.
                candidates = [i + 1 for i in range(start + MIN_CHARS, end)
                              if excerpt[i] in ".!?؟۔\n"]
                if not candidates:
                    candidates = [i + 1 for i in range(start + MIN_CHARS, end)
                                  if excerpt[i].isspace()]
                if candidates:
                    end = candidates[-1]
            while end > start and excerpt[end - 1].isspace():
                end -= 1
            if end <= start:
                break
            if end - start < MIN_CHARS:
                if positions and end - positions[-1][0] <= MAX_CHARS:
                    positions[-1] = (positions[-1][0], end)
                break
            positions.append((start, end))
            start = end
        for n, (a, b) in enumerate(positions, start=1):
            if len(out) >= MAX_PASSAGES:
                return tuple(out)
            out.append(Passage(f"{sid}.P{n}", sid, excerpt[a:b], a, b))
    return tuple(out)
