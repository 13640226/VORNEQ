"""Global AI V1: bounded public web retrieval behind a replaceable interface.

Security model (see docs/ai/GLOBAL_AI_V1_CONTRACT.md):
* No arbitrary URL fetching. Each provider owns a FIXED host allowlist and
  builds the request URL itself; user text is only an encoded query value.
* SSRF: every resolved address must be globally routable; the TLS connection
  is pinned to the vetted address (no DNS rebinding between check and use).
* Redirects are refused, timeouts and response size are bounded.
* Results are untrusted data: normalized, length-bounded, deduplicated and
  given explicit provenance. Source identity is never taken from the model.
Mock providers are permitted only in tests and must be marked synthetic.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import ssl
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

from apps.ai_core.sanitization import UnsafePrompt, screen_and_redact

MAX_RESULTS = 3
TIMEOUT_S = 5.0
MAX_RESPONSE_BYTES = 262_144
MAX_TITLE = 140
MAX_EXCERPT = 500
USER_AGENT = "VORNEQ-GlobalAI/1.0 (grounded citations; contact via repository 13640226/VORNEQ)"

# Invisible bidi/format controls common in Persian web text. ZWNJ (U+200C) is
# a legitimate Persian character and is kept.
_INVISIBLE = re.compile("[\u200b\u200e\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\u00ad]")


class RetrievalError(RuntimeError):
    """Controlled retrieval failure; message never contains response bodies."""


class RetrievalTimeout(RetrievalError):
    pass


@dataclass(frozen=True)
class WebEvidence:
    source_key: str
    title: str
    url: str
    publisher: str
    excerpt: str
    retrieved_at: str
    published_at: str | None = None


def clean_text(value, maximum: int) -> str:
    """NFC-normalize, drop invisible controls (keep ZWNJ), collapse whitespace,
    cut at a word boundary. Never returns markup interpretation."""
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFC", _INVISIBLE.sub("", value))
    value = "".join(
        ch if ch == "\u200c" or not unicodedata.category(ch).startswith("C") else " "
        for ch in value
    )
    value = " ".join(value.split())
    if len(value) <= maximum:
        return value
    cut = value[:maximum]
    space = cut.rfind(" ")
    return (cut[:space] if space > maximum // 2 else cut).rstrip()


def _is_public_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to a vetted IP while verifying the certificate for ``host``."""

    def __init__(self, host: str, address: str, timeout: float):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self._vetted_address = address

    def connect(self):
        sock = socket.create_connection((self._vetted_address, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def safe_get_json(host: str, path: str, params: dict, *, allowed_hosts: frozenset,
                  timeout: float = TIMEOUT_S, max_bytes: int = MAX_RESPONSE_BYTES,
                  resolver=socket.getaddrinfo, connection_class=_PinnedHTTPSConnection):
    """GET https://<allowlisted host><fixed path>?<encoded params> and parse JSON."""
    if host not in allowed_hosts or not re.fullmatch(r"[a-z0-9.-]{1,100}", host):
        raise RetrievalError("host not allowlisted")
    if not path.startswith("/") or "//" in path or "\\" in path or "?" in path:
        raise RetrievalError("invalid request path")
    try:
        infos = resolver(host, 443, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as exc:
        raise RetrievalError("resolution failed") from exc
    addresses = sorted({info[4][0] for info in infos if info and len(info) >= 5})
    if not addresses or not all(_is_public_address(a) for a in addresses):
        raise RetrievalError("non-public address refused")
    connection = connection_class(host, addresses[0], timeout)
    try:
        connection.request("GET", path + "?" + urlencode(params), headers={
            "User-Agent": USER_AGENT, "Accept": "application/json",
            "Accept-Encoding": "identity",
        })
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise RetrievalError("redirect refused")
        if response.status != 200:
            raise RetrievalError("unexpected status")
        content_type = (response.getheader("Content-Type") or "").lower()
        if not content_type.startswith("application/json"):
            raise RetrievalError("unexpected content type")
        declared = response.getheader("Content-Length")
        if declared is not None and (not declared.isdecimal() or int(declared) > max_bytes):
            raise RetrievalError("response too large")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise RetrievalError("response too large")
        return json.loads(body.decode("utf-8"))
    except (socket.timeout, TimeoutError) as exc:
        raise RetrievalTimeout("search timed out") from exc
    except RetrievalError:
        raise
    except (OSError, ssl.SSLError, http.client.HTTPException, UnicodeError, ValueError) as exc:
        raise RetrievalError("search transport failed") from exc
    finally:
        connection.close()


class PublicWebRetriever:
    """Replaceable interface. Implementations must return WebEvidence only."""

    name = "abstract"
    allowed_hosts: frozenset = frozenset()

    def search(self, query: str, language: str, limit: int = MAX_RESULTS) -> tuple[WebEvidence, ...]:
        raise NotImplementedError


class WikipediaRetriever(PublicWebRetriever):
    """Wikimedia Action API: one bounded request per question, no API key.

    Chosen for V1 because it is public, multilingual (fa/de/en), keyless, has a
    fixed host per language and returns plain-text extracts. It is a tertiary
    source: answers must cite it as such and must not be presented as verified.
    """

    name = "wikipedia"
    source_type = "encyclopedia"
    licence = "CC BY-SA 4.0 (text); attribution via linked page"
    HOSTS = {"fa": "fa.wikipedia.org", "de": "de.wikipedia.org", "en": "en.wikipedia.org"}
    allowed_hosts = frozenset(HOSTS.values())
    _KEY = re.compile(r"web:wikipedia:(fa|de|en):[1-9][0-9]{0,11}\Z")

    def __init__(self, *, fetch=safe_get_json, clock=None):
        self._fetch = fetch
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _page_url(self, value, host):
        if not isinstance(value, str) or len(value) > 400:
            return None
        parts = urlsplit(value)
        if (parts.scheme != "https" or parts.hostname != host or parts.port is not None
                or parts.username or parts.password or not parts.path.startswith("/wiki/")
                or parts.query or parts.fragment or any(ord(c) < 33 for c in value)):
            return None
        return value

    def search(self, query, language, limit=MAX_RESULTS):
        if language not in self.HOSTS:
            raise RetrievalError("unsupported language")
        try:
            query = screen_and_redact(" ".join(str(query).split()), limit=200)
        except UnsafePrompt as exc:
            raise RetrievalError("unsafe query") from exc
        if not query or "[REDACTED_" in query:
            # Never send redacted personal data or secrets to a third party.
            raise RetrievalError("query contains personal data")
        limit = max(1, min(int(limit), MAX_RESULTS))
        host = self.HOSTS[language]
        payload = self._fetch(host, "/w/api.php", {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrsearch": query, "gsrlimit": str(limit),
            "gsrnamespace": "0", "prop": "extracts|info", "exintro": "1",
            "explaintext": "1", "exchars": "700", "inprop": "url", "maxlag": "5",
        }, allowed_hosts=self.allowed_hosts)
        pages = payload.get("query", {}).get("pages", []) if isinstance(payload, dict) else []
        if not isinstance(pages, list):
            return ()
        retrieved_at = self._clock().replace(microsecond=0).isoformat()
        ordered = sorted((p for p in pages if isinstance(p, dict)),
                         key=lambda p: p.get("index") if isinstance(p.get("index"), int) else 99)
        results, seen = [], set()
        for page in ordered:
            pageid = page.get("pageid")
            if type(pageid) is not int or pageid <= 0:
                continue
            key = f"web:wikipedia:{language}:{pageid}"
            url = self._page_url(page.get("fullurl"), host)
            title = clean_text(page.get("title"), MAX_TITLE)
            excerpt = clean_text(page.get("extract"), MAX_EXCERPT)
            if (not self._KEY.fullmatch(key) or not url or not title or len(excerpt) < 40
                    or key in seen or url in seen):
                continue
            seen.update((key, url))
            results.append(WebEvidence(key, title, url, f"Wikipedia ({language})",
                                       excerpt, retrieved_at, None))
            if len(results) == limit:
                break
        return tuple(results)


def default_retriever() -> PublicWebRetriever:
    return WikipediaRetriever()
