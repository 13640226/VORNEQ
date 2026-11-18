"""Global AI V2: provider registry and fail-closed multi-source retrieval.

Only providers registered HERE (code-reviewed, fixed host allowlists) can be
enabled, and only through ``settings.VORNEQ_GLOBAL_AI_PROVIDERS``. Unknown
names fail closed. Users can never supply a provider, host or URL.
"""
from __future__ import annotations

from apps.ai_core.web_retrieval import (MAX_RESULTS, PublicWebRetriever, RetrievalError,
                                        RetrievalTimeout, WebEvidence, WikipediaRetriever)

# name -> factory. A new provider is added only after its API, licence, terms
# and security constraints are verified and documented (GLOBAL_AI_V2_CONTRACT §4).
PROVIDERS = {
    "wikipedia": WikipediaRetriever,
}
DEFAULT_PROVIDERS = ("wikipedia",)
MAX_PROVIDERS = 3
PER_PROVIDER_LIMIT = MAX_RESULTS
MAX_CANDIDATES = MAX_PROVIDERS * PER_PROVIDER_LIMIT


class MultiSourceRetriever(PublicWebRetriever):
    """Query each configured provider once, sequentially and bounded.

    * A provider raising RetrievalError (expected, controlled) is recorded and
      skipped while at least one other provider succeeds.
    * Any other exception, a non-WebEvidence result or a result whose host is
      outside that provider's allowlist fails the whole request closed.
    * If every provider fails, the first timeout (else the first error) is raised.
    """

    name = "multi"

    def __init__(self, retrievers, *, max_results=MAX_RESULTS):
        if type(max_results) is not int or not 1 <= max_results <= 5:
            raise RetrievalError("invalid candidate limit")
        self.max_results = max_results
        retrievers = tuple(retrievers)
        if not 1 <= len(retrievers) <= MAX_PROVIDERS:
            raise RetrievalError("invalid provider configuration")
        names = [getattr(r, "name", "") for r in retrievers]
        if len(set(names)) != len(names) or not all(isinstance(n, str) and n for n in names):
            raise RetrievalError("invalid provider configuration")
        self.retrievers = retrievers
        self.allowed_hosts = frozenset().union(*(frozenset(r.allowed_hosts) for r in retrievers))
        self.last_status = ()

    def search(self, query, language, limit=PER_PROVIDER_LIMIT):
        limit = max(1, min(int(limit), self.max_results))
        collected, status, errors = [], [], []
        for retriever in self.retrievers:
            try:
                items = retriever.search(query, language, limit=limit)
            except RetrievalError as exc:
                status.append((retriever.name, "timeout" if isinstance(exc, RetrievalTimeout) else "error"))
                errors.append(exc)
                continue
            except Exception as exc:  # unexpected: fail closed, never partially trust
                raise RetrievalError("unexpected provider failure") from exc
            if not isinstance(items, tuple) or len(items) > limit:
                raise RetrievalError("provider returned an invalid result set")
            for item in items:
                if not isinstance(item, WebEvidence):
                    raise RetrievalError("provider returned untrusted evidence")
                host = _host(item.url)
                if host not in retriever.allowed_hosts:
                    raise RetrievalError("provider returned evidence outside its allowlist")
            status.append((retriever.name, "ok" if items else "empty"))
            collected.extend(items)
        self.last_status = tuple(status)
        if errors and len(errors) == len(self.retrievers):
            timeouts = [e for e in errors if isinstance(e, RetrievalTimeout)]
            raise timeouts[0] if timeouts else errors[0]
        return tuple(collected[:MAX_PROVIDERS * self.max_results])


def _host(url):
    from urllib.parse import urlsplit
    try:
        return urlsplit(url).hostname if isinstance(url, str) else None
    except ValueError:
        return None


def configured_provider_names():
    from django.conf import settings
    names = getattr(settings, "VORNEQ_GLOBAL_AI_PROVIDERS", DEFAULT_PROVIDERS)
    if (not isinstance(names, (tuple, list)) or not 1 <= len(names) <= MAX_PROVIDERS
            or len(set(names)) != len(names) or any(n not in PROVIDERS for n in names)):
        raise RetrievalError("invalid provider configuration")
    return tuple(names)


def default_retriever(*, max_results=MAX_RESULTS, max_excerpt=500, exchars=700) -> MultiSourceRetriever:
    names = configured_provider_names()
    if (max_results, max_excerpt, exchars) == (MAX_RESULTS, 500, 700):
        return MultiSourceRetriever(PROVIDERS[name]() for name in names)
    # V3 currently authorizes *only* the existing code-reviewed Wikipedia host.
    if names != ("wikipedia",):
        raise RetrievalError("unsupported Stage 2 provider configuration")
    wiki = WikipediaRetriever(max_results=max_results, max_excerpt=max_excerpt, exchars=exchars)
    return MultiSourceRetriever((wiki,), max_results=max_results)
