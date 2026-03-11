"""Typed models for manual security evaluation datasets and run artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pathfinder.errors import ValidationError
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider
from pathfinder.security_evaluators.models import AttackTransitionCandidate, SecurityScoreBreakdown, VALID_ATTACK_TYPES
from pathfinder.structural.enums import RelationshipType
from pathfinder.structural.ids import normalize_repo_path


class EvaluationVersion(StrEnum):
    V1 = "v1"


class RiskLabel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def risk_label_from_score(score: float) -> RiskLabel:
    if score >= 0.75:
        return RiskLabel.CRITICAL
    if score >= 0.5:
        return RiskLabel.HIGH
    if score >= 0.25:
        return RiskLabel.MEDIUM
    return RiskLabel.LOW


def is_high_risk(label: RiskLabel) -> bool:
    return label in {RiskLabel.HIGH, RiskLabel.CRITICAL}


class PricingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_token_price_per_1m_usd: float | None = Field(default=None, ge=0.0)
    output_token_price_per_1m_usd: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_pairing(self) -> "PricingConfig":
        provided = [
            self.input_token_price_per_1m_usd is not None,
            self.output_token_price_per_1m_usd is not None,
        ]
        if any(provided) and not all(provided):
            raise ValidationError("PricingConfig requires both input and output token pricing values")
        return self


class ModelProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: LLMProvider
    model: str
    total_context_tokens: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    pricing: PricingConfig | None = None


class FileRiskGoldenCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    file_path: str
    expected_risk_score: float = Field(ge=0.0, le=1.0)
    expected_risk_label: RiskLabel
    rationale: str

    @field_validator("file_path")
    @classmethod
    def normalize_file_path(cls, value: str) -> str:
        return normalize_repo_path(value)

    @model_validator(mode="after")
    def validate_risk_label(self) -> "FileRiskGoldenCase":
        derived = risk_label_from_score(self.expected_risk_score)
        if derived != self.expected_risk_label:
            raise ValidationError(
                "File risk case label does not match expected_risk_score",
                context={
                    "case_id": self.case_id,
                    "expected_risk_score": self.expected_risk_score,
                    "derived_label": derived.value,
                    "expected_risk_label": self.expected_risk_label.value,
                },
            )
        return self


class AttackEdgeGoldenCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    structural_edge_id: str
    source_path: str
    target_path: str
    relationship_type: RelationshipType
    expected_attack_edge: bool
    expected_attack_types: list[str] = Field(default_factory=list)
    expected_primary_attack_type: str | None = None
    expected_edge_attack_cost: float | None = Field(default=None, ge=0.0)
    rationale: str

    @field_validator("source_path", "target_path")
    @classmethod
    def normalize_paths(cls, value: str) -> str:
        return normalize_repo_path(value)

    @field_validator("expected_attack_types")
    @classmethod
    def validate_attack_types(cls, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value not in VALID_ATTACK_TYPES:
                raise ValidationError("Attack edge case references unsupported attack type", context={"attack_type": value})
            if value not in deduped:
                deduped.append(value)
        return deduped

    @model_validator(mode="after")
    def validate_attack_expectations(self) -> "AttackEdgeGoldenCase":
        if self.expected_attack_edge and not self.expected_attack_types:
            raise ValidationError("Positive attack edge cases must declare expected_attack_types", context={"case_id": self.case_id})
        if not self.expected_attack_edge and self.expected_attack_types:
            raise ValidationError("Negative attack edge cases must not declare expected_attack_types", context={"case_id": self.case_id})
        if not self.expected_attack_edge and self.expected_primary_attack_type is not None:
            raise ValidationError("Negative attack edge cases must not declare expected_primary_attack_type", context={"case_id": self.case_id})
        if not self.expected_attack_edge and self.expected_edge_attack_cost is not None:
            raise ValidationError("Negative attack edge cases must not declare expected_edge_attack_cost", context={"case_id": self.case_id})
        if self.expected_primary_attack_type is not None and self.expected_primary_attack_type not in self.expected_attack_types:
            raise ValidationError(
                "expected_primary_attack_type must be included in expected_attack_types",
                context={"case_id": self.case_id, "expected_primary_attack_type": self.expected_primary_attack_type},
            )
        return self


class EvaluationDatasetSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    file_case_count: int
    attack_edge_case_count: int
    high_risk_file_count: int
    positive_attack_edge_case_count: int


class EvaluationDatasetDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    notes: list[str] = Field(default_factory=list)


class EvaluationDatasetArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_id: str
    version: EvaluationVersion = EvaluationVersion.V1
    repo_path: str
    file_risk_cases: list[FileRiskGoldenCase]
    attack_edge_cases: list[AttackEdgeGoldenCase]
    summary: EvaluationDatasetSummary
    diagnostics: EvaluationDatasetDiagnostics = Field(default_factory=EvaluationDatasetDiagnostics)

    @model_validator(mode="after")
    def validate_integrity(self) -> "EvaluationDatasetArtifact":
        file_case_ids = [case.case_id for case in self.file_risk_cases]
        attack_case_ids = [case.case_id for case in self.attack_edge_cases]
        if len(file_case_ids) != len(set(file_case_ids)):
            raise ValidationError("Duplicate file risk case ids detected in evaluation dataset")
        if len(attack_case_ids) != len(set(attack_case_ids)):
            raise ValidationError("Duplicate attack edge case ids detected in evaluation dataset")

        file_paths = [case.file_path for case in self.file_risk_cases]
        if len(file_paths) != len(set(file_paths)):
            raise ValidationError("Evaluation dataset contains duplicate file risk file_path values")

        structural_edge_ids = [case.structural_edge_id for case in self.attack_edge_cases]
        if len(structural_edge_ids) != len(set(structural_edge_ids)):
            raise ValidationError("Evaluation dataset contains duplicate structural_edge_id values")

        high_risk_count = sum(1 for case in self.file_risk_cases if is_high_risk(case.expected_risk_label))
        positive_attack_edge_count = sum(1 for case in self.attack_edge_cases if case.expected_attack_edge)
        if self.summary.file_case_count != len(self.file_risk_cases):
            raise ValidationError("Dataset summary file_case_count does not match serialized file_risk_cases")
        if self.summary.attack_edge_case_count != len(self.attack_edge_cases):
            raise ValidationError("Dataset summary attack_edge_case_count does not match serialized attack_edge_cases")
        if self.summary.high_risk_file_count != high_risk_count:
            raise ValidationError("Dataset summary high_risk_file_count does not match file_risk_cases")
        if self.summary.positive_attack_edge_case_count != positive_attack_edge_count:
            raise ValidationError("Dataset summary positive_attack_edge_case_count does not match attack_edge_cases")
        return self


class FileRiskPredictionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    security_scores: SecurityScoreBreakdown
    normalized_risk_score: float = Field(ge=0.0, le=1.0)


class PredictedAttackEdgeSnapshot(AttackTransitionCandidate):
    model_config = ConfigDict(frozen=True)

    id: str | None = None
    source: str | None = None
    target: str | None = None
    structural_basis_edge_ids: list[str] = Field(default_factory=list)
    excluded_flag: bool = False


class FileRiskEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    file_path: str
    expected_risk_score: float = Field(ge=0.0, le=1.0)
    expected_risk_label: RiskLabel
    expected_high_risk: bool
    predicted_risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    predicted_risk_label: RiskLabel | None = None
    predicted_high_risk: bool | None = None
    score_absolute_error: float | None = Field(default=None, ge=0.0)
    label_match: bool | None = None
    high_risk_match: bool | None = None
    prediction: FileRiskPredictionSnapshot | None = None
    llm_invocation: LLMInvocationRecord | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    error_message: str | None = None

    @field_validator("file_path")
    @classmethod
    def normalize_file_path(cls, value: str) -> str:
        return normalize_repo_path(value)


class AttackEdgeEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    structural_edge_id: str
    source_path: str
    target_path: str
    relationship_type: RelationshipType
    expected_attack_edge: bool
    expected_attack_types: list[str] = Field(default_factory=list)
    expected_primary_attack_type: str | None = None
    expected_edge_attack_cost: float | None = Field(default=None, ge=0.0)
    predicted_has_attack: bool | None = None
    predicted_attack_types: list[str] = Field(default_factory=list)
    top_1_attack_type: str | None = None
    predicted_edge_attack_cost: float | None = Field(default=None, ge=0.0)
    presence_match: bool | None = None
    relaxed_attack_type_match: bool | None = None
    exact_attack_type_match: bool | None = None
    attack_type_jaccard: float | None = Field(default=None, ge=0.0, le=1.0)
    edge_attack_cost_absolute_error: float | None = Field(default=None, ge=0.0)
    predicted_attacks: list[PredictedAttackEdgeSnapshot] = Field(default_factory=list)
    llm_invocation: LLMInvocationRecord | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    error_message: str | None = None

    @field_validator("source_path", "target_path")
    @classmethod
    def normalize_paths(cls, value: str) -> str:
        return normalize_repo_path(value)

    @field_validator("expected_attack_types", "predicted_attack_types")
    @classmethod
    def dedupe_attack_types(cls, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped


class FileRiskMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_count: int
    completed_case_count: int
    error_case_count: int
    label_accuracy: float | None = None
    score_mean_absolute_error: float | None = None
    high_risk_precision: float | None = None
    high_risk_recall: float | None = None
    high_risk_f1: float | None = None
    true_positive_count: int = 0
    false_positive_count: int = 0
    false_negative_count: int = 0
    true_negative_count: int = 0
    expected_label_distribution: dict[str, int] = Field(default_factory=dict)
    predicted_label_distribution: dict[str, int] = Field(default_factory=dict)
    label_confusion_matrix: dict[str, dict[str, int]] = Field(default_factory=dict)


class AttackEdgeMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_count: int
    completed_case_count: int
    error_case_count: int
    positive_case_count: int
    predicted_positive_count: int
    presence_accuracy: float | None = None
    presence_precision: float | None = None
    presence_recall: float | None = None
    presence_f1: float | None = None
    relaxed_attack_type_accuracy: float | None = None
    exact_attack_type_accuracy: float | None = None
    top_1_attack_type_accuracy: float | None = None
    average_attack_type_jaccard: float | None = None
    edge_attack_cost_mean_absolute_error: float | None = None
    true_positive_count: int = 0
    false_positive_count: int = 0
    false_negative_count: int = 0
    true_negative_count: int = 0


class RuntimeMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    invocation_count: int
    missing_usage_count: int = 0
    missing_cost_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_duration_seconds: float = 0.0
    average_duration_seconds: float = 0.0
    median_duration_seconds: float = 0.0
    p95_duration_seconds: float = 0.0
    max_duration_seconds: float = 0.0
    estimated_total_cost_usd: float | None = None


class EvaluationRunSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_case_count: int
    completed_case_count: int
    error_case_count: int
    file_case_count: int
    attack_edge_case_count: int
    risk_threshold: float = Field(ge=0.0, le=1.0)
    runtime: RuntimeMetrics
    file_risk: FileRiskMetrics
    attack_edges: AttackEdgeMetrics


class EvaluationRunDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    missing_file_paths: list[str] = Field(default_factory=list)
    file_error_case_ids: list[str] = Field(default_factory=list)
    attack_edge_error_case_ids: list[str] = Field(default_factory=list)
    missing_usage_case_ids: list[str] = Field(default_factory=list)
    missing_cost_case_ids: list[str] = Field(default_factory=list)


class EvaluationRunArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    version: EvaluationVersion = EvaluationVersion.V1
    dataset_id: str
    repo_path: str
    provider: LLMProvider
    model: str
    model_profile: ModelProfile | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    pricing: PricingConfig | None = None
    file_results: list[FileRiskEvaluationResult]
    attack_edge_results: list[AttackEdgeEvaluationResult]
    summary: EvaluationRunSummary
    diagnostics: EvaluationRunDiagnostics

    @model_validator(mode="after")
    def validate_integrity(self) -> "EvaluationRunArtifact":
        completed_file_cases = sum(1 for result in self.file_results if result.error_message is None)
        completed_attack_cases = sum(1 for result in self.attack_edge_results if result.error_message is None)
        error_file_cases = len(self.file_results) - completed_file_cases
        error_attack_cases = len(self.attack_edge_results) - completed_attack_cases
        invocation_count = sum(
            1 for result in [*self.file_results, *self.attack_edge_results] if result.llm_invocation is not None
        )
        if self.summary.file_case_count != len(self.file_results):
            raise ValidationError("Run summary file_case_count does not match file_results")
        if self.summary.attack_edge_case_count != len(self.attack_edge_results):
            raise ValidationError("Run summary attack_edge_case_count does not match attack_edge_results")
        if self.summary.total_case_count != len(self.file_results) + len(self.attack_edge_results):
            raise ValidationError("Run summary total_case_count does not match serialized results")
        if self.summary.completed_case_count != completed_file_cases + completed_attack_cases:
            raise ValidationError("Run summary completed_case_count does not match serialized results")
        if self.summary.error_case_count != error_file_cases + error_attack_cases:
            raise ValidationError("Run summary error_case_count does not match serialized results")
        if self.summary.file_risk.case_count != len(self.file_results):
            raise ValidationError("File risk metrics case_count does not match file_results")
        if self.summary.file_risk.completed_case_count != completed_file_cases:
            raise ValidationError("File risk metrics completed_case_count does not match file_results")
        if self.summary.file_risk.error_case_count != error_file_cases:
            raise ValidationError("File risk metrics error_case_count does not match file_results")
        if self.summary.attack_edges.case_count != len(self.attack_edge_results):
            raise ValidationError("Attack edge metrics case_count does not match attack_edge_results")
        if self.summary.attack_edges.completed_case_count != completed_attack_cases:
            raise ValidationError("Attack edge metrics completed_case_count does not match attack_edge_results")
        if self.summary.attack_edges.error_case_count != error_attack_cases:
            raise ValidationError("Attack edge metrics error_case_count does not match attack_edge_results")
        if self.summary.runtime.invocation_count != invocation_count:
            raise ValidationError("Runtime metrics invocation_count does not match serialized results")
        return self