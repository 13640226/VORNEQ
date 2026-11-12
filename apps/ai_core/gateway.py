"""Phase A Global AI: public-only, bounded citations and fail-closed drafts."""
from __future__ import annotations
import re
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
    # Explicitly construct public adapters. Private Documents / held Media
    # cannot be included by a later change to UnifiedSearch default adapters.
    from apps.search.services import (ArticleAdapter, ProductAdapter,
                                      LibraryItemAdapter, AudioItemAdapter, UnifiedSearch)
    adapters = [ArticleAdapter(), ProductAdapter(), LibraryItemAdapter(), AudioItemAdapter()]
    payload = UnifiedSearch(adapters=adapters).search(
        query=question, filters={}, page=1, page_size=3, language=language)
    return public_citations(payload)

def valid_cited_draft(text, citations):
    # Provenance syntax ONLY; not factual verification.
    if not isinstance(text, str) or not text.strip() or len(text) > 1800:
        return False
    cited = set(re.findall(r"\[S\d+\]", text))
    known = {"[" + item.id + "]" for item in citations}
    return bool(cited) and cited.issubset(known)

def ask_public(question, language, *, allow_model=False, egress_enabled=False,
               provider=None, retrieval=None):
    question, language = validate(question, language)
    sources = tuple((retrieval or retrieve_public)(question, language))
    if any(not isinstance(s, Citation) for s in sources) or len(sources) > 3:
        raise InputError("invalid retrieved evidence")
    if sources and allow_model and egress_enabled and provider:
        try:
            text = provider.generate(question=question, language=language, sources=sources)
            if valid_cited_draft(text, sources):
                return {"mode": "model_draft", "answer": text, "language": language,
                        "citations": [s.as_dict() for s in sources], "verified": False,
                        "model_status": "draft_unverified"}
        except Exception:
            # Do not leak provider errors or source context in responses/logs.
            pass
    return {"mode": "sources_only" if sources else "no_sources",
            "answer": MESSAGES[language][0 if sources else 1].format(n=len(sources)),
            "language": language, "citations": [s.as_dict() for s in sources],
            "verified": False,
            "model_status": ("disabled" if not egress_enabled else
                             "not_requested" if not allow_model else "unavailable_or_invalid")}
