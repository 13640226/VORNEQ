"""Typed interface for mock or real (optional) grounded provider."""
from typing import Protocol


class GroundedProvider(Protocol):
    def generate(self, *, question: str, language: str, sources: list[dict]) -> dict:
        """Return parsed response dictionary or raise GatewayError."""
