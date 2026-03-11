"""Typed models for security evaluation LLM outputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


VALID_ATTACK_TYPES: tuple[str, ...] = (
    "sql_injection",
    "broken_authentication",
    "broken_authorization",
    "idor",
    "unsafe_deserialization",
    "command_injection",
    "session_abuse",
    "privilege_propagation",
    "unsafe_database_access",
)

VALID_REQUIRED_CAPABILITIES: tuple[str, ...] = ("low", "med", "high")


class SecurityScoreBreakdown(BaseModel):
    model_config = ConfigDict(frozen=True)

    exploitability: float
    privilege_gain: float
    data_access_value: float
    lateral_movement_value: float
    detection_risk: float
    confidence: float


class FileSecurityAnalysisPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    tags: list[str] = Field(default_factory=list)
    confidence: float
    rationale: str
    security_scores: SecurityScoreBreakdown


class AttackTransitionCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    attack_type: str
    transition_likelihood: float
    required_capability: str
    detection_risk: float
    edge_attack_cost: float
    confidence: float
    rationale: str


class EdgeSecurityAnalysisPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    attacks: list[AttackTransitionCandidate] = Field(default_factory=list)
