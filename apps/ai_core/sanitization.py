"""Defense-in-depth filter, NOT a complete prompt-injection or PII detector.

Source content remains untrusted even after screening. Never splice retrieved
text into the system/developer instruction channel. Valid Persian ZWNJ (U+200C)
is supported; other invisible formatting controls fail closed.
"""
import re
import unicodedata

_INJECTION = re.compile(
    r"(?i)(ignore\s+(all\s+)?previous\s+instructions|"
    r"(^|\n)\s*(system|developer|assistant)\s*:|"
    r"<\s*/?\s*(system|developer)\s*>|"
    r"\[im_start\]|<\|im_start\|>|"
    r"base64\s*(decode|encoded|:))"
)
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\s().-]?){9,15}(?!\w)")
_SECRET = re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{10,}|Bearer\s+[A-Za-z0-9._-]{12,})\b")


class UnsafePrompt(ValueError):
    pass


def screen_and_redact(value: str, *, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise UnsafePrompt("input too long")
    if any(unicodedata.category(c) in ("Cf", "Cs") and c != "\u200c" for c in value):
        raise UnsafePrompt("hidden/control characters")
    if _INJECTION.search(value):
        raise UnsafePrompt("embedded instruction pattern")
    cleaned = _SECRET.sub("[REDACTED_SECRET]", value)
    cleaned = _EMAIL.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _PHONE.sub("[REDACTED_PHONE]", cleaned)
    if any(ord(c) < 32 and c not in "\n\t" for c in cleaned):
        raise UnsafePrompt("control characters")
    return cleaned.strip()
