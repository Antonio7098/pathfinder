"""Typed boundary models for recommendation report inputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pathfinder.errors import ValidationError
from pathfinder.reporting.enums import GraphScope, RecommendationInputVersion
from pathfinder.structural.ids import normalize_repo_path


class ReportFileReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    reason: str | None = None

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return normalize_repo_path(value)


class PathNodeInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    path: str
    language: str
    display_name: str | None = None
    role: str | None = None
    target_flag: bool = False
    normalized_risk_score: float | None = None
    confidence: float | None = None
    rationale: str | None = None
    backing_file_paths: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return normalize_repo_path(value)

    @field_validator("backing_file_paths")
    @classmethod
    def normalize_backing_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class PathEdgeInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    target: str
    relationship_type: str | None = None
    attack_type: str | None = None
    edge_attack_cost: float | None = None
    confidence: float | None = None
    rationale: str | None = None
    structural_basis_edge_ids: list[str] = Field(default_factory=list)


class RecommendationReportInputSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    path_node_count: int
    path_edge_count: int
    focal_file_count: int


class RecommendationReportInputArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_artifact_id: str
    version: RecommendationInputVersion = RecommendationInputVersion.V1
    repo_path: str
    graph_scope: GraphScope = GraphScope.FILE
    graph_id: str | None = None
    path_id: str
    path_nodes: list[PathNodeInput]
    path_edges: list[PathEdgeInput]
    focal_files: list[ReportFileReference] = Field(default_factory=list)
    summary: RecommendationReportInputSummary

    @model_validator(mode="after")
    def validate_integrity(self) -> "RecommendationReportInputArtifact":
        if not self.path_nodes:
            raise ValidationError("Recommendation report input requires at least one path node", context={"path_id": self.path_id})

        node_ids = [node.id for node in self.path_nodes]
        edge_ids = [edge.id for edge in self.path_edges]
        if len(node_ids) != len(set(node_ids)):
            raise ValidationError("Duplicate path node ids detected", context={"path_id": self.path_id, "node_ids": node_ids})
        if len(edge_ids) != len(set(edge_ids)):
            raise ValidationError("Duplicate path edge ids detected", context={"path_id": self.path_id, "edge_ids": edge_ids})

        expected_edge_count = max(len(self.path_nodes) - 1, 0)
        if len(self.path_edges) != expected_edge_count:
            raise ValidationError(
                "Path edge count does not match ordered path nodes",
                context={"path_id": self.path_id, "expected": expected_edge_count, "actual": len(self.path_edges)},
            )

        node_id_set = set(node_ids)
        for index, edge in enumerate(self.path_edges):
            if edge.source not in node_id_set or edge.target not in node_id_set:
                raise ValidationError(
                    "Path edge references missing path node",
                    context={"path_id": self.path_id, "edge_id": edge.id, "source": edge.source, "target": edge.target},
                )
            expected_source = self.path_nodes[index].id
            expected_target = self.path_nodes[index + 1].id
            if edge.source != expected_source or edge.target != expected_target:
                raise ValidationError(
                    "Path edges must align with ordered path nodes",
                    context={
                        "path_id": self.path_id,
                        "edge_id": edge.id,
                        "expected_source": expected_source,
                        "expected_target": expected_target,
                        "actual_source": edge.source,
                        "actual_target": edge.target,
                    },
                )

        if self.graph_scope == GraphScope.SERVICE:
            for node in self.path_nodes:
                if not node.backing_file_paths:
                    raise ValidationError(
                        "Service-scope recommendation input nodes must include backing_file_paths",
                        context={"path_id": self.path_id, "node_id": node.id},
                    )

        if self.summary.path_node_count != len(self.path_nodes):
            raise ValidationError(
                "Input summary path_node_count does not match serialized nodes",
                context={"expected": len(self.path_nodes), "actual": self.summary.path_node_count},
            )
        if self.summary.path_edge_count != len(self.path_edges):
            raise ValidationError(
                "Input summary path_edge_count does not match serialized edges",
                context={"expected": len(self.path_edges), "actual": self.summary.path_edge_count},
            )
        if self.summary.focal_file_count != len(self.focal_files):
            raise ValidationError(
                "Input summary focal_file_count does not match serialized focal files",
                context={"expected": len(self.focal_files), "actual": self.summary.focal_file_count},
            )
        return self
