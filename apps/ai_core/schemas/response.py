"""Minimal strict schema for OpenAI Structured Outputs (validated again locally).

Avoid minLength/maxLength/minItems JSON Schema keywords unsupported by some
Structured Outputs model configurations. Local citation.py enforces all bounds.
"""
from pydantic import BaseModel, ConfigDict


class GroundedCitationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str
    evidence_digest: str
    evidence_quote: str


class GroundedAnswerSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str
    language: str
    citations: list[GroundedCitationSchema]
    model_status: str
    grounded_status: str
    verified: bool
    error_code: str
