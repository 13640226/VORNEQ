"""Deterministic guard for uncited (model-knowledge) answers.

Rejects links, DOI references and pseudo-source markers in prose, while allowing URLs
inside properly tagged, closed fenced code blocks (legitimate programming examples).

Code blocks are never an escape hatch:
- untagged, text-like (text, markdown, ...), unknown-tag and UNCLOSED fences are
  scanned exactly like prose;
- inside accepted code blocks, citation-labelled lines ("Source: <url>") and bare-URL
  lines are rejected; DOI references are rejected everywhere.

The answer is never rewritten: it is either accepted unchanged or rejected.
Scanning uses a normalized copy (NFKC, zero-width characters removed) so that
full-width or zero-width obfuscation of "https://" does not evade the checks.

Known residual risk (documented, not hidden): a URL or source name inside a code
string or in a comment that also contains other words (print("https://...") or
"# See <url> for details") is indistinguishable from a legitimate example.
"""
from __future__ import annotations

import re
import unicodedata

_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
_DIGIT = r"[0-9\u0660-\u0669\u06f0-\u06f9]"
_LABEL = (r"(?:sources?|references?|citations?|bibliography|quellen?|quellenangaben|"
          r"literatur|literaturverzeichnis|\u0645\u0646\u0627\u0628\u0639|\u0645\u0646\u0628\u0639|"
          r"\u0645\u0631\u0627\u062c\u0639)")

_SCHEME_OR_WWW = re.compile(r"(?i)\b[a-z][a-z0-9+.\-]*://|\bwww\.")
_DOI = re.compile(r"(?i)\bdoi:\s*10\.|\bdoi\.org/")
_MD_PROTOCOL_RELATIVE = re.compile(r"\]\([ \t]*//")
_REFERENCE_DEFINITION = re.compile(r"^[ \t]*\[[^\]]{1,40}\]:[ \t]*\S+")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_MARKER = re.compile(r"(?<![\w\]\)])\[" + _DIGIT + r"{1,3}\](?![\w(\[])")
_LABEL_LINE = re.compile(r"(?i)^[ \t#>*_\-]*" + _LABEL + r"[ \t*_]*:[ \t*_]*(?:$|\[" + _DIGIT + r"{1,3}\])")
_HEADING_LINE = re.compile(r"(?i)^[ \t>]*(?:#{1,6}[ \t]*|[*_]{2}[ \t]*)" + _LABEL + r"[ \t*_]*:?[ \t*_]*$")

_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})([^`]*)$")
_FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
_TAG = re.compile(r"[ \t]*\{?\.?([A-Za-z0-9_+#\-]+)")

_COMMENT_LINE = re.compile(r"^[ \t]*(?:#|//|--|/\*|\*|;|<!--)")
_COMMENT_PREFIX = re.compile(r"^[ \t#/*;<!>\-]*")
_CODE_LABEL = re.compile(r"(?i)" + _LABEL + r"[ \t]*:")
_BARE_URL = re.compile(r"(?i)^(?:[a-z][a-z0-9+.\-]*://|www\.)\S*$")

# Configuration/markup languages: URLs are ordinary values there, so only COMMENT
# lines are checked for citation labels and bare URLs.
_STRUCTURED_TAGS = frozenset({"json", "yaml", "yml", "toml", "ini", "xml", "html", "css", "http"})
_CODE_TAGS = _STRUCTURED_TAGS | frozenset({
    "python", "py", "python3", "javascript", "js", "typescript", "ts", "jsx", "tsx",
    "bash", "sh", "shell", "zsh", "powershell", "ps1", "cmd", "bat", "sql", "java",
    "kotlin", "c", "cpp", "c++", "csharp", "cs", "go", "rust", "rs", "ruby", "rb",
    "php", "swift", "r", "dockerfile", "makefile", "graphql", "lua", "perl", "scala",
    "dart", "groovy", "haskell", "elixir", "clojure", "matlab", "julia", "vb", "vba",
    "fsharp", "objectivec", "diff", "regex",
})


def _tag(info):
    match = _TAG.match(info or "")
    return match.group(1).lower() if match else ""


def _split_blocks(text):
    prose, blocks, pending, fence = [], [], [], None
    for line in text.splitlines():
        if fence is None:
            opener = _FENCE_OPEN.match(line)
            if opener:
                marker, info = opener.groups()
                fence = (marker[0], len(marker), _tag(info))
                pending = []
                prose.append(info)  # the info string itself is plain text
            else:
                prose.append(line)
            continue
        closer = _FENCE_CLOSE.match(line)
        if closer and closer.group(1)[0] == fence[0] and len(closer.group(1)) >= fence[1]:
            if fence[2] in _CODE_TAGS:
                blocks.append((fence[2], pending))
            else:
                prose.extend(pending)
            fence, pending = None, []
        else:
            pending.append(line)
    if fence is not None:  # unclosed fence: nothing may hide in it
        prose.extend(pending)
    return prose, blocks


def find_violation(answer):
    """Return None if acceptable, else a short reason code (never the content)."""
    text = unicodedata.normalize("NFKC", answer).translate(_INVISIBLE)
    if _DOI.search(text):
        return "doi"
    prose, blocks = _split_blocks(text)
    joined = "\n".join(prose)
    if _SCHEME_OR_WWW.search(joined) or _MD_PROTOCOL_RELATIVE.search(joined):
        return "link"
    if any(_REFERENCE_DEFINITION.match(line) for line in prose):
        return "link"
    for line in prose:
        visible = _INLINE_CODE.sub(" ", line)
        if _LABEL_LINE.match(visible) or _HEADING_LINE.match(visible) or _MARKER.search(visible):
            return "source_marker"
    for tag, lines in blocks:
        structured = tag in _STRUCTURED_TAGS
        for line in lines:
            if structured and not _COMMENT_LINE.match(line):
                continue
            stripped = _COMMENT_PREFIX.sub("", line).strip()
            if _CODE_LABEL.match(stripped) and _SCHEME_OR_WWW.search(stripped):
                return "code_citation"
            if _BARE_URL.match(stripped.strip("\"'<>()[], ")):
                return "code_citation"
    return None