"""Fail-closed, deterministic policy for a future uncited general-knowledge mode.

This module does not authorize provider calls or change the grounded pipeline.
All existing actor, ledger, recovery, and emergency-stop gates remain upstream.
"""
from __future__ import annotations

from django.conf import settings

from apps.ai_core.global_router import GENERAL_PUBLIC, route_question


def general_knowledge_candidate(question: str, fallback_language: str = "en") -> bool:
    """Only classify an eligible public question; never authorize a provider call."""
    if getattr(settings, "VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED", False) is not True:
        return False
    route = route_question(question, fallback_language)
    return route.kind == GENERAL_PUBLIC
