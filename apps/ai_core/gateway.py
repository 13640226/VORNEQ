"""Phase A Offline AI Core: bounded public citations; no LLM/egress path."""
from __future__ import annotations

from dataclasses import dataclass

PUBLIC_PREFIXES = {"article": "article:", "product": "product:", "audio": "audio:"}
PUBLIC_LIBRARY_TYPES = {"libraryitem", "book", "article", "document", "other"}
MESSAGES = {
    "fa": ("{n} منبع عمومی مرتبط پیدا شد. ارجاعات را بررسی کنید؛ این پاسخ تأییدشدهٔ هوش مصنوعی نیست.",
           "منبع عمومی مرتبط پیدا نشد؛ پاسخ بدون سند تولید نمی‌شود."),
    "en": ("Found {n} public sources. Review the citations; this is not a verified AI answer.",
           "No matching public sources; no unsupported answer was generated."),
    "de": ("{n} öffentliche Quellen gefunden. Bitte Belege prüfen; dies ist keine verifizierte KI-Antwort.",
           "Keine passenden öffentlichen Quellen; keine unbelegte Antwort erzeugt."),
}


class InputError(ValueError):
    pass


def validate(question, language):
    if not isinstance(question, str):
        raise InputError("question must be text")
    question = " ".join(question.split())
    if not question or len(question) > 200 or any(ord(c) < 32 for c in question):
        raise InputError("question must be 1-200 printable characters")
    if language not in MESSAGES:
        raise InputError("unsupported language")
    return question, language


def _text(value, maximum):
    return " ".join(value.split())[:maximum] if isinstance(value, str) else ""


def _url(value):
    if not isinstance(value, str) or len(value) > 300:
        return None
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    if any(ord(c) < 32 for c in value):
        return None
    return value


@dataclass(frozen=True)
class Citation:
    id: str
    key: str
    title: str
    excerpt: str
    url: str | None

    def as_dict(self):
        return {"id": self.id, "key": self.key, "title": self.title,
                "excerpt": self.excerpt, "url": self.url}


def public_citations(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        return ()
    items, seen = [], set()
    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        key, kind = item.get("key"), item.get("type")
        if not isinstance(key, str) or len(key) > 100 or key in seen:
            continue
        prefix = ("library:" if kind in PUBLIC_LIBRARY_TYPES and key.startswith("library:")
                  else PUBLIC_PREFIXES.get(kind))
        if not prefix or not key.startswith(prefix):
            continue
        title = _text(item.get("title"), 140)
        if not title:
            continue
        seen.add(key)
        items.append(Citation("S" + str(len(items) + 1), key, title,
                              _text(item.get("description"), 300), _url(item.get("url"))))
        if len(items) == 3:
            break
    return tuple(items)


def retrieve_public(question, language):
    """Find published evidence without treating conversational wording as a title.

    The fallback is intentionally narrow: only an explicit VORNEQ name query
    can use a shorter search term. No private documents, media or seed products.
    """
    import re
    from apps.search.services import (ArticleAdapter, ProductAdapter,
                                      LibraryItemAdapter, AudioItemAdapter, UnifiedSearch)

    adapters = [ArticleAdapter(), ProductAdapter(), LibraryItemAdapter(), AudioItemAdapter()]
    search = UnifiedSearch(adapters=adapters)
    payload = search.search(
        query=question, filters={}, page=1, page_size=3, language=language)
    citations = public_citations(payload)
    if citations:
        return citations

    # A full natural-language question is rarely an exact substring of a
    # published title or summary. Retry only for the explicit platform name.
    if not re.search(r"(?i)(?<![a-z0-9])vorneq(?![a-z0-9])", question):
        return ()
    # Platform identity answers must come from published editorial/library
    # material, not marketplace listings (which may include synthetic seeds).
    editorial = UnifiedSearch(adapters=[ArticleAdapter(), LibraryItemAdapter()])
    payload = editorial.search(
        query="vorneq", filters={}, page=1, page_size=3, language=language)
    if not isinstance(payload, dict):
        return ()
    # Defense in depth: a malformed search result must not inject products
    # into the editorial-only fallback.
    items = payload.get("results")
    if not isinstance(items, list):
        return ()
    return public_citations({
        "results": [item for item in items if isinstance(item, dict)
                    and (item.get("type") == "article"
                         or (item.get("type") in PUBLIC_LIBRARY_TYPES
                             and str(item.get("key", "")).startswith("library:")))]
    })


def ask_public(question, language, *, retrieval=None):
    """Return citations only. No provider, tools, generated draft or model invocation."""
    question, language = validate(question, language)
    sources = tuple((retrieval or retrieve_public)(question, language))
    if any(not isinstance(s, Citation) for s in sources) or len(sources) > 3:
        raise InputError("invalid retrieved evidence")
    return {"mode": "sources_only" if sources else "no_sources",
            "answer": MESSAGES[language][0 if sources else 1].format(n=len(sources)),
            "language": language, "citations": [s.as_dict() for s in sources],
            "verified": False, "model_status": "offline_only"}
