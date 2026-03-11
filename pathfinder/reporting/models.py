"""Typed models for persisted recommendation report artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pathfinder.errors import ValidationError
from pathfinder.llm.models import LLMInvocationRecord
from pathfinder.reporting.enums import GraphScope, RecommendationPriority, RecommendationReportVersion, RecommendationTemplateVersion
from pathfinder.structural.ids import normalize_repo_path


class LLMRecommendationItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    priority: RecommendationPriority
    title: str
    summary: str
    mitigation_steps: list[str]
    primary_file_path: str
    supporting_file_paths: list[str] = Field(default_factory=list)
    supporting_node_ids: list[str] = Field(default_factory=list)
    supporting_edge_ids: list[str] = Field(default_factory=list)
    confidence: float

    @field_validator("primary_file_path")
    @classmethod
    def normalize_primary_file_path(cls, value: str) -> str:
        return normalize_repo_path(value)

    @field_validator("supporting_file_paths")
    @classmethod
    def normalize_supporting_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class LLMRecommendationReportPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    path_narrative: str
    target_rationale: str
    top_priority_file_path: str
    top_priority_rationale: str
    recommendations: list[LLMRecommendationItem]

    @field_validator("top_priority_file_path")
    @classmethod
    def normalize_top_priority_file_path(cls, value: str) -> str:
        return normalize_repo_path(value)


class RecommendationPathOverview(BaseModel):
    model_config = ConfigDict(frozen=True)

    path_id: str
    graph_scope: GraphScope = GraphScope.FILE
    ordered_node_ids: list[str]
    ordered_edge_ids: list[str]
    ordered_file_paths: list[str]
    path_narrative: str
    target_rationale: str
    top_priority_file_path: str
    top_priority_rationale: str

    @field_validator("ordered_file_paths")
    @classmethod
    def normalize_ordered_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]

    @field_validator("top_priority_file_path")
    @classmethod
    def normalize_top_priority_file_path(cls, value: str) -> str:
        return normalize_repo_path(value)


class RecommendationItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    priority: RecommendationPriority
    title: str
    summary: str
    mitigation_steps: list[str]
    primary_file_path: str
    supporting_file_paths: list[str] = Field(default_factory=list)
    supporting_node_ids: list[str] = Field(default_factory=list)
    supporting_edge_ids: list[str] = Field(default_factory=list)
    confidence: float

    @field_validator("primary_file_path")
    @classmethod
    def normalize_primary_file_path(cls, value: str) -> str:
        return normalize_repo_path(value)

    @field_validator("supporting_file_paths")
    @classmethod
    def normalize_supporting_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class RecommendationReportSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    path_node_count: int
    path_edge_count: int
    known_file_count: int
    loaded_file_count: int
    missing_file_count: int
    truncated_file_count: int
    dropped_file_count: int
    recommendation_count: int
    citation_count: int


class RecommendationReportDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    missing_file_paths: list[str] = Field(default_factory=list)
    truncated_file_paths: list[str] = Field(default_factory=list)
    dropped_file_paths: list[str] = Field(default_factory=list)
    total_prompt_chars: int = 0

    @field_validator("missing_file_paths", "truncated_file_paths", "dropped_file_paths")
    @classmethod
    def normalize_file_path_lists(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class RecommendationReportArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_id: str
    version: RecommendationReportVersion = RecommendationReportVersion.V1
    template_version: RecommendationTemplateVersion
    input_artifact_id: str
    repo_path: str
    known_file_paths: list[str]
    path_overview: RecommendationPathOverview
    recommendations: list[RecommendationItem]
    llm_invocation: LLMInvocationRecord
    summary: RecommendationReportSummary
    diagnostics: RecommendationReportDiagnostics

    @field_validator("known_file_paths")
    @classmethod
    def normalize_known_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]

    @model_validator(mode="after")
    def validate_integrity(self) -> "RecommendationReportArtifact":
        known_file_set = set(self.known_file_paths)
        node_id_set = set(self.path_overview.ordered_node_ids)
        edge_id_set = set(self.path_overview.ordered_edge_ids)

        if self.path_overview.top_priority_file_path not in known_file_set:
            raise ValidationError(
                "Top priority file path is not grounded in known files",
                context={"top_priority_file_path": self.path_overview.top_priority_file_path},
            )

        citation_count = 0
        for recommendation in self.recommendations:
            if recommendation.primary_file_path not in known_file_set:
                raise ValidationError(
                    "Recommendation cites an unknown primary file path",
                    context={"recommendation_id": recommendation.id, "primary_file_path": recommendation.primary_file_path},
                )
            citation_count += 1
            for file_path in recommendation.supporting_file_paths:
                if file_path not in known_file_set:
                    raise ValidationError(
                        "Recommendation cites an unknown supporting file path",
                        context={"recommendation_id": recommendation.id, "file_path": file_path},
                    )
                citation_count += 1
            for node_id in recommendation.supporting_node_ids:
                if node_id not in node_id_set:
                    raise ValidationError(
                        "Recommendation cites an unknown supporting node id",
                        context={"recommendation_id": recommendation.id, "node_id": node_id},
                    )
                citation_count += 1
            for edge_id in recommendation.supporting_edge_ids:
                if edge_id not in edge_id_set:
                    raise ValidationError(
                        "Recommendation cites an unknown supporting edge id",
                        context={"recommendation_id": recommendation.id, "edge_id": edge_id},
                    )
                citation_count += 1

        if self.summary.path_node_count != len(self.path_overview.ordered_node_ids):
            raise ValidationError(
                "Report summary path_node_count does not match serialized path nodes",
                context={"expected": len(self.path_overview.ordered_node_ids), "actual": self.summary.path_node_count},
            )
        if self.summary.path_edge_count != len(self.path_overview.ordered_edge_ids):
            raise ValidationError(
                "Report summary path_edge_count does not match serialized path edges",
                context={"expected": len(self.path_overview.ordered_edge_ids), "actual": self.summary.path_edge_count},
            )
        if self.summary.known_file_count != len(self.known_file_paths):
            raise ValidationError(
                "Report summary known_file_count does not match serialized known files",
                context={"expected": len(self.known_file_paths), "actual": self.summary.known_file_count},
            )
        if self.summary.recommendation_count != len(self.recommendations):
            raise ValidationError(
                "Report summary recommendation_count does not match serialized recommendations",
                context={"expected": len(self.recommendations), "actual": self.summary.recommendation_count},
            )
        if self.summary.citation_count != citation_count:
            raise ValidationError(
                "Report summary citation_count does not match serialized citations",
                context={"expected": citation_count, "actual": self.summary.citation_count},
            )
        return self
