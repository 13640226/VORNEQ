"""V7-02 — Zentrale, modellabhängige Limit-Policy und Token-Budget-Engine.

Eine Quelle für alle Chat-Grenzen (Eingabe, Ausgabe, Kontext, Verlauf, Request-
Größe). Sie ersetzt die verstreuten Festwerte (200 Zeichen, 2048 Bytes,
8192-Pilot-Obergrenze, 6400/1400 Zeichen) durch eine Policy pro Modell.

Grundsätze (ADR-0008):

* **Fail-closed.** Ohne gültige, vollständige Konfiguration gilt die bisherige
  Policy (``LEGACY``) unverändert: 200 Zeichen, 2048 Bytes, bisherige
  Ausgabe- und Verlaufsgrenzen. Unbekannte Werte werden nie geraten.
* **Keine neuen Variablen ohne Not.** Es werden die bestehenden Settings
  ``VORNEQ_AI_CHAT_BUDGET_MODEL``, ``VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS``,
  ``VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET`` und ``VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET``
  genutzt; für Production zusätzlich das ausdrückliche Opt-in
  ``VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT`` (Name und Semantik aus PR #712).
* **Konservative Token-Schätzung.** Für byte-level-BPE-Tokenizer (OpenAI) ist
  die Zahl der UTF-8-Bytes eine harte Obergrenze der Tokenzahl; dazu kommt ein
  fester Rahmen je Nachricht. Zeichen werden nie als Tokens gezählt.
  Provider ohne bekannte Strategie erhalten keine erweiterten Grenzen.
* **Ledger bleibt maßgeblich.** Größere Grenzen erhöhen nur, was die Ledger-
  Reservierung (tatsächliche Payload-Bytes + ``max_output_tokens``) abdecken
  muss; die Reservierung ist und bleibt die Zahlungsgrenze.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from django.conf import settings

from apps.ai_core.provider_registry import CATALOG, NOT_VERIFIED, ModelUnavailable

# --------------------------------------------------------------- Konstanten
LEGACY_MESSAGE_CHARS = 200          # bisherige Produktgrenze (Fallback)
LEGACY_REQUEST_BYTES = 2048         # bisherige Body-Grenze (Fallback)
MIN_INPUT_TOKENS = 512              # untere Grenze einer erweiterten Policy
MIN_OUTPUT_TOKENS = 1536
MIN_CONTEXT_TOKENS = 8192
MAX_CONTEXT_TOKENS = 1_000_000
HARD_MAX_OUTPUT_TOKENS = 131_072  # absolute Obergrenze je Antwort, unabhängig vom Modell
MAX_VALIDATED_ANSWER_CHARS = 8 * HARD_MAX_OUTPUT_TOKENS      # Plausibilitätsgrenze für Konfigurationswerte
# Harte Request-Obergrenze, unabhängig vom Modell (Missbrauchsschutz,
# Speicher/CPU vor teurer Verarbeitung). Liegt unter Djangos
# DATA_UPLOAD_MAX_MEMORY_SIZE (2,5 MiB).
HARD_MAX_REQUEST_BYTES = 2 * 1024 * 1024
JSON_ESCAPE_FACTOR = 6              # \uXXXX: bis zu 6 Bytes je Eingabezeichen
JSON_FRAME_BYTES = 512
MESSAGE_FRAME_TOKENS = 8            # Rollen-/Nachrichtenrahmen je Turn (konservativ)
SYSTEM_PROMPT_RESERVE_TOKENS = 4000  # Anweisungen + Schema (vgl. INPUT_OVERHEAD_TOKENS)
RETRIEVAL_RESERVE_TOKENS = 5 * 1500 * 4  # V7-02-Wert (Stage 2), nur noch Referenz/Kompatibilität
# V7-02.1: Retrieval-Reserve aus den tatsächlichen Retrieval-Grenzen der Umgebung.
# Je Quelle: Excerpt + quote_hint (80) + Titel (≤ 300) in 4 UTF-8-Bytes plus
# 512 Bytes für source_id, Digest und JSON-Rahmen (konservativ).
SOURCE_TITLE_MAX_CHARS = 300
SOURCE_QUOTE_HINT_CHARS = 80
SOURCE_FRAME_BYTES = 512
TOOL_CONTEXT_TOKENS = 0             # V7-02: keine Tools
ATTACHMENT_BYTES = 0                # V7-02: keine Anhänge
SAFETY_MARGIN_RATIO = 0.05
MIN_SAFETY_MARGIN_TOKENS = 512
ANSWER_CHARS_PER_TOKEN = 8          # Validierungs-Obergrenze, kein Tokenizer

TOKENIZER_UTF8_UPPER_BOUND = "utf8_bytes_upper_bound"
TOKENIZER_BY_PROVIDER = {"openai-text": TOKENIZER_UTF8_UPPER_BOUND}

SOURCE_LEGACY = "LEGACY_DEFAULT"
SOURCE_CONFIGURED = "OPERATOR_CONFIGURED"
SOURCE_PILOT = "INPUT_PILOT"          # bisheriger Eingabe-Pilot (≤ 8192, ohne Kontextangabe)
PILOT_MAX_INPUT_TOKENS = 8192


class LimitError(ValueError):
    code = "limit_error"


class InputTooLarge(LimitError):
    code = "INPUT_TOO_LARGE"


class ContextLimitExceeded(LimitError):
    code = "CONTEXT_LIMIT_EXCEEDED"


# --------------------------------------------------------- Token-Schätzung
def estimate_tokens(text: str, *, strategy: str = TOKENIZER_UTF8_UPPER_BOUND) -> int:
    """Konservative Obergrenze der Tokenzahl eines Textes.

    ``utf8_bytes_upper_bound``: byte-level BPE erzeugt höchstens ein Token je
    Byte; Persisch (2 Bytes/Zeichen), Deutsch (Umlaute 2 Bytes) und Emoji
    (4 Bytes) werden dadurch automatisch höher bewertet als ASCII.
    """
    if strategy != TOKENIZER_UTF8_UPPER_BOUND:
        raise LimitError("unknown tokenizer strategy")
    if not isinstance(text, str):
        raise LimitError("text expected")
    try:
        return len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:  # einzelne Surrogates
        raise LimitError("invalid unicode") from exc


def estimate_message_tokens(text: str, *, strategy: str = TOKENIZER_UTF8_UPPER_BOUND) -> int:
    return estimate_tokens(text, strategy=strategy) + MESSAGE_FRAME_TOKENS


# ------------------------------------------------------------------ Policy
@dataclass(frozen=True)
class ModelLimits:
    """COR-01: effektive Grenzen eines Chat-Modells in einer Umgebung."""

    model_id: str
    provider_id: str
    context_window: int | None
    max_input_tokens: int
    max_output_tokens: int
    max_request_bytes: int
    max_message_characters: int
    max_history_tokens: int | None
    max_attachment_bytes: int = ATTACHMENT_BYTES
    reserved_output_tokens: int = 0
    system_prompt_tokens: int = SYSTEM_PROMPT_RESERVE_TOKENS
    tool_context_tokens: int = TOOL_CONTEXT_TOKENS
    retrieval_context_tokens: int = RETRIEVAL_RESERVE_TOKENS
    # V7-02.1: Ausgabe-Policy gilt für alle Pfade (nicht nur Stage 2), sobald
    # die Policy vollständig konfiguriert ist; siehe ``policy_output_tokens``.
    token_safety_margin: int = 0
    tokenizer_strategy: str | None = None
    pricing_reference: str | None = None
    verification_status: str = NOT_VERIFIED
    verified_at: str | None = None
    source: str = SOURCE_LEGACY
    conflicts: tuple = field(default_factory=tuple)

    @property
    def extended(self) -> bool:
        """Vollständige Modell-Policy mit Kontextfenster (Planung möglich)."""
        return self.source == SOURCE_CONFIGURED

    @property
    def widened_input(self) -> bool:
        return self.source in (SOURCE_CONFIGURED, SOURCE_PILOT)

    @property
    def answer_chars(self) -> int:
        """Obergrenze für die Validierung einer Modellantwort (kein Tokenizer)."""
        return ANSWER_CHARS_PER_TOKEN * self.max_output_tokens


def _bounded(raw, minimum, maximum):
    if (not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal()
            or len(raw) > 7):
        return None
    value = int(raw)
    return value if minimum <= value <= maximum else None


def _legacy(environment, conflicts=()):
    from apps.ai_core.response_engine_v3 import output_tokens
    return ModelLimits(
        model_id="", provider_id="openai-text", context_window=None,
        max_input_tokens=LEGACY_MESSAGE_CHARS, max_output_tokens=output_tokens(settings),
        max_request_bytes=LEGACY_REQUEST_BYTES, max_message_characters=LEGACY_MESSAGE_CHARS,
        max_history_tokens=None, reserved_output_tokens=output_tokens(settings),
        tokenizer_strategy=None, source=SOURCE_LEGACY, conflicts=tuple(conflicts),
    )


def _hosted_prerequisites():
    from apps.ai_core.request_recovery import enabled as recovery_enabled
    from apps.ai_ledger.service import ledger_enabled
    return ledger_enabled() and recovery_enabled()


def _pilot(environment, max_input, conflicts=()):
    """Bisheriger Eingabe-Pilot (≤ 8192): Eingabegrenze ohne Kontextplanung."""
    if max_input > PILOT_MAX_INPUT_TOKENS:
        return _legacy(environment, list(conflicts) + ["context_window_required_above_8192"])
    if environment in ("staging", "production") and not _hosted_prerequisites():
        return _legacy(environment, list(conflicts) + ["ledger_or_recovery_unavailable"])
    legacy = _legacy(environment)
    return ModelLimits(
        model_id="", provider_id="openai-text", context_window=None,
        max_input_tokens=max_input, max_output_tokens=legacy.max_output_tokens,
        max_request_bytes=JSON_ESCAPE_FACTOR * max_input + JSON_FRAME_BYTES,
        max_message_characters=max_input, max_history_tokens=None,
        reserved_output_tokens=legacy.max_output_tokens,
        tokenizer_strategy=TOKENIZER_UTF8_UPPER_BOUND, source=SOURCE_PILOT, conflicts=tuple(conflicts),
    )


def retrieval_reserve_tokens() -> int:
    """Obergrenze der Quellen-Tokens gemäß den wirksamen Retrieval-Grenzen."""
    from apps.ai_core.response_engine_v3 import retrieval_limits
    results, excerpt = retrieval_limits(settings)
    per_source = 4 * (excerpt + SOURCE_QUOTE_HINT_CHARS + SOURCE_TITLE_MAX_CHARS) + SOURCE_FRAME_BYTES
    return results * per_source


def safety_margin(context_window: int) -> int:
    return max(MIN_SAFETY_MARGIN_TOKENS, int(context_window * SAFETY_MARGIN_RATIO))


def chat_limits() -> ModelLimits:
    """Effektive Chat-Policy für die aktuelle Umgebung (nur Konfiguration, keine Anfragen).

    Erweiterte Grenzen nur wenn **alle** Bedingungen gelten, sonst ``LEGACY``:
    bekannte Umgebung; Production nur mit exakt ``True``-Opt-in; gehostet nur mit
    Ledger und Request-Recovery; Budget-Modell gleich ``VORNEQ_AI_PHASE_B_MODEL``;
    Provider mit bekannter Tokenizer-Strategie; plausible Werte, die zusammen
    in das Kontextfenster passen.
    """
    environment = getattr(settings, "VORNEQ_ENV", None)
    if environment not in ("development", "staging", "production"):
        return _legacy(environment, ["invalid_environment"])
    raw_input = getattr(settings, "VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET", "")
    if not raw_input:
        return _legacy(environment)
    conflicts = []
    if environment == "production" and getattr(settings, "VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT", False) is not True:
        return _legacy(environment, ["production_opt_in_missing"])
    max_input = _bounded(raw_input, MIN_INPUT_TOKENS, MAX_CONTEXT_TOKENS)
    if max_input is None:
        return _legacy(environment, ["input_budget_invalid"])
    model = getattr(settings, "VORNEQ_AI_CHAT_BUDGET_MODEL", "")
    context_raw = getattr(settings, "VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS", "")
    if not model and not context_raw:
        return _pilot(environment, max_input)
    if not isinstance(model, str) or not model or len(model) > 100:
        return _legacy(environment, ["budget_model_missing"])
    if model != os.environ.get("VORNEQ_AI_PHASE_B_MODEL", ""):
        return _legacy(environment, ["budget_model_mismatch"])
    provider_id = "openai-text"
    strategy = TOKENIZER_BY_PROVIDER.get(provider_id)
    if strategy is None:
        return _legacy(environment, ["tokenizer_unknown"])
    context = _bounded(getattr(settings, "VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS", ""),
                       MIN_CONTEXT_TOKENS, MAX_CONTEXT_TOKENS)
    if context is None:
        return _legacy(environment, ["context_window_invalid"])
    # Registry-Werte (falls je verifiziert) begrenzen die Konfiguration nach oben.
    pricing, status, verified_at = None, NOT_VERIFIED, None
    try:
        spec = CATALOG.model(provider_id, model)
    except ModelUnavailable:
        spec = None
    if spec is not None:
        pricing, status, verified_at = spec.pricing_reference, spec.availability_status, spec.pricing_verified_at
        if spec.context_window:
            if context > spec.context_window:
                conflicts.append("context_window_above_registry")
            context = min(context, spec.context_window)
    margin = safety_margin(context)
    output = _bounded(getattr(settings, "VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET", ""), MIN_OUTPUT_TOKENS, min(context, HARD_MAX_OUTPUT_TOKENS))
    if output is None:
        from apps.ai_core.response_engine_v3 import output_tokens
        output = output_tokens(settings)
    if spec is not None and spec.max_output_tokens and output > spec.max_output_tokens:
        conflicts.append("output_above_registry")
        output = spec.max_output_tokens
    retrieval_reserve = retrieval_reserve_tokens()
    available_input = context - output - SYSTEM_PROMPT_RESERVE_TOKENS - retrieval_reserve - margin
    if available_input < MIN_INPUT_TOKENS:
        # Zu kleines Fenster für die volle Planung: bisheriger Pilot (die
        # Provider-Kontextprüfung bleibt wie zuvor die harte Grenze).
        return _pilot(environment, max_input, ["context_too_small_for_reservations"])
    if max_input > available_input:
        conflicts.append("input_budget_above_context")
        max_input = available_input
    if spec is not None and spec.max_input_tokens and max_input > spec.max_input_tokens:
        conflicts.append("input_above_registry")
        max_input = spec.max_input_tokens
    if environment in ("staging", "production") and not _hosted_prerequisites():
        return _legacy(environment, ["ledger_or_recovery_unavailable"])
    request_bytes = min(HARD_MAX_REQUEST_BYTES, JSON_ESCAPE_FACTOR * max_input + JSON_FRAME_BYTES)
    if request_bytes < JSON_ESCAPE_FACTOR * max_input + JSON_FRAME_BYTES:
        conflicts.append("request_bytes_hard_cap")
        max_input = (request_bytes - JSON_FRAME_BYTES) // JSON_ESCAPE_FACTOR
    history = context - output - max_input - SYSTEM_PROMPT_RESERVE_TOKENS - retrieval_reserve - margin
    return ModelLimits(
        model_id=model, provider_id=provider_id, context_window=context,
        max_input_tokens=max_input, max_output_tokens=output, max_request_bytes=request_bytes,
        # Jedes Zeichen kostet mindestens ein Byte (≥ ein geschätztes Token):
        # die Zeichengrenze ist daher nie großzügiger als die Tokengrenze.
        max_message_characters=max_input, max_history_tokens=max(0, history),
        reserved_output_tokens=output, token_safety_margin=margin, tokenizer_strategy=strategy,
        retrieval_context_tokens=retrieval_reserve,
        pricing_reference=pricing, verification_status=status if spec else NOT_VERIFIED,
        verified_at=verified_at, source=SOURCE_CONFIGURED, conflicts=tuple(conflicts),
    )


# ------------------------------------------------------- Kontext-Planung
@dataclass(frozen=True)
class ContextPlan:
    """COR-03: Zusammensetzung einer Anfrage in geschätzten Tokens (Obergrenzen)."""

    context_window: int
    system_prompt: int
    user_prompt: int
    history: int
    retrieved_sources: int
    tool_context: int
    attachments: int
    reserved_output: int
    safety_margin: int

    @property
    def input_total(self) -> int:
        return (self.system_prompt + self.user_prompt + self.history + self.retrieved_sources
                + self.tool_context + self.attachments)

    @property
    def total(self) -> int:
        return self.input_total + self.reserved_output + self.safety_margin

    @property
    def fits(self) -> bool:
        return self.total <= self.context_window


def plan_context(limits: ModelLimits, *, system_prompt="", user_prompt="", history=(), sources_text="",
                 tool_context="", attachments_bytes=0, raise_on_overflow=True) -> ContextPlan:
    if not limits.extended or limits.context_window is None:
        raise ContextLimitExceeded("no verified context policy")
    strategy = limits.tokenizer_strategy
    plan = ContextPlan(
        context_window=limits.context_window,
        system_prompt=estimate_tokens(system_prompt, strategy=strategy),
        user_prompt=estimate_message_tokens(user_prompt, strategy=strategy),
        history=sum(estimate_message_tokens(turn.get("content", ""), strategy=strategy) for turn in history),
        retrieved_sources=estimate_tokens(sources_text, strategy=strategy),
        tool_context=estimate_tokens(tool_context, strategy=strategy),
        attachments=int(attachments_bytes),
        reserved_output=limits.reserved_output_tokens,
        safety_margin=limits.token_safety_margin,
    )
    if raise_on_overflow and not plan.fits:
        raise ContextLimitExceeded("context window exceeded")
    return plan


def fits_input_bytes(limits: ModelLimits, input_bytes: int, overhead_tokens: int) -> bool:
    """Prüfung der tatsächlichen Payload-Bytes (Anweisungen + Payload) vor dem Aufruf."""
    if not limits.extended or limits.context_window is None:
        return True  # Legacy: keine Kontextprüfung (bisheriges Verhalten)
    return (input_bytes + overhead_tokens + limits.reserved_output_tokens
            + limits.token_safety_margin) <= limits.context_window


def select_history(pairs_newest_first, limits: ModelLimits, *, budget=None):
    """COR-05: Verlauf nach Token-Budget statt fester Nachrichtenzahl.

    ``pairs_newest_first``: [(frage, antwort), ...] ab dem neuesten Paar.
    Rückgabe: Turns ältestes→neuestes; ein Paar wird ganz oder gar nicht
    übernommen, die Reihenfolge bleibt erhalten, der gespeicherte Verlauf
    bleibt unverändert (nur die gesendete Auswahl wird begrenzt).
    """
    budget = (limits.max_history_tokens or 0) if budget is None else budget
    strategy = limits.tokenizer_strategy
    selected, used = [], 0
    for question, answer in pairs_newest_first:
        size = (estimate_message_tokens(question, strategy=strategy)
                + estimate_message_tokens(answer, strategy=strategy))
        if used + size > budget:
            break
        selected.append(({"role": "user", "content": question}, {"role": "assistant", "content": answer}))
        used += size
    return tuple(turn for pair in reversed(selected) for turn in pair)


def history_budget(limits: ModelLimits, user_prompt: str = "") -> int:
    """COR-07 (V7-02.1): dynamisches Verlaufsbudget für eine konkrete Anfrage.

    Statt die volle Eingabegrenze fest zu reservieren, wird nur die tatsächliche
    Größe der aktuellen Nachricht abgezogen. Ergebnis ist nie kleiner als das
    statische ``max_history_tokens`` und nie negativ; die Summe aller Teile bleibt
    ≤ Kontextfenster (System, Quellen, Ausgabe und Marge bleiben reserviert).
    """
    if not limits.extended or limits.context_window is None:
        return 0
    static = limits.max_history_tokens or 0
    prompt = estimate_message_tokens(user_prompt or "", strategy=limits.tokenizer_strategy)
    if prompt > limits.max_input_tokens:
        return static
    dynamic = (limits.context_window - limits.reserved_output_tokens - limits.system_prompt_tokens
               - limits.retrieval_context_tokens - limits.tool_context_tokens
               - limits.max_attachment_bytes - limits.token_safety_margin - prompt)
    return max(0, static, dynamic)


def policy_output_tokens(model: str) -> int | None:
    """COR-08 (V7-02.1): konfigurierte Ausgabe-Tokens für ``model``, sonst ``None``.

    Nur bei vollständiger Policy (``OPERATOR_CONFIGURED``) und exakt dem
    konfigurierten Modell; Production setzt dafür das exakte Opt-in, Ledger und
    Recovery voraus (siehe ``chat_limits``). Die Ledger-Reservierung folgt
    automatisch diesem Wert (``BudgetedProvider`` reserviert ``max_output_tokens``).
    """
    limits = chat_limits()
    if not limits.extended or not model or limits.model_id != model:
        return None
    return limits.max_output_tokens


def describe(limits: ModelLimits) -> dict:
    """Bericht/Diagnose ohne Secrets (Modellname nur bei Konfiguration aus Settings)."""
    return {
        "source": limits.source,
        "model_configured": bool(limits.model_id),
        "provider_id": limits.provider_id,
        "context_window": limits.context_window,
        "max_input_tokens": limits.max_input_tokens,
        "max_output_tokens": limits.max_output_tokens,
        "reserved_output_tokens": limits.reserved_output_tokens,
        "max_request_bytes": limits.max_request_bytes,
        "max_message_characters": limits.max_message_characters,
        "max_history_tokens": limits.max_history_tokens,
        "max_attachment_bytes": limits.max_attachment_bytes,
        "system_prompt_tokens": limits.system_prompt_tokens,
        "tool_context_tokens": limits.tool_context_tokens,
        "retrieval_context_tokens": limits.retrieval_context_tokens,
        "token_safety_margin": limits.token_safety_margin,
        "tokenizer_strategy": limits.tokenizer_strategy or "NONE (legacy limits)",
        "pricing_reference": limits.pricing_reference or NOT_VERIFIED,
        "verification_status": limits.verification_status,
        "verified_at": limits.verified_at,
        "answer_chars": limits.answer_chars,
        "conflicts": list(limits.conflicts),
    }
