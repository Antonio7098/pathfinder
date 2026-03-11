"""Pydantic models for service grouping and derived service graph artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pathfinder.errors import ValidationError
from pathfinder.llm.models import LLMInvocationRecord
from pathfinder.services.enums import ServiceAssignmentKind, ServiceGraphVersion, ServiceGroupingVersion, ServiceKind, ServiceLayer, ServiceResolutionSource, ServiceTemplateVersion
from pathfinder.structural.ids import normalize_repo_path


class LLMProposedService(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    layer: ServiceLayer = ServiceLayer.UNKNOWN
    summary: str
    file_paths: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str | None = None

    @field_validator("file_paths")
    @classmethod
    def normalize_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class LLMServiceGroupingPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    architecture_summary: str
    services: list[LLMProposedService]
    shared_file_paths: list[str] = Field(default_factory=list)
    unclassified_file_paths: list[str] = Field(default_factory=list)

    @field_validator("shared_file_paths", "unclassified_file_paths")
    @classmethod
    def normalize_path_lists(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class ServiceDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: ServiceKind = ServiceKind.INFERRED
    layer: ServiceLayer = ServiceLayer.UNKNOWN
    summary: str
    member_file_paths: list[str]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None

    @field_validator("member_file_paths")
    @classmethod
    def normalize_member_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class ServiceFileAssignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    file_path: str
    assigned_service_id: str
    assignment_kind: ServiceAssignmentKind
    resolution_source: ServiceResolutionSource
    proposed_service_ids: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None

    @field_validator("file_path")
    @classmethod
    def normalize_file_path(cls, value: str) -> str:
        return normalize_repo_path(value)


class ServiceGroupingSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_count: int
    inferred_service_count: int
    file_count: int
    shared_file_count: int
    unclassified_file_count: int
    ambiguous_file_count: int
    invented_file_reference_count: int
    dropped_service_count: int


class ServiceGroupingDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_file_count: int = 0
    prompt_edge_count: int = 0
    total_prompt_chars: int = 0
    invented_file_paths: list[str] = Field(default_factory=list)
    overlap_file_paths: list[str] = Field(default_factory=list)
    shared_file_paths: list[str] = Field(default_factory=list)
    unclassified_file_paths: list[str] = Field(default_factory=list)
    connectivity_promoted_file_paths: list[str] = Field(default_factory=list)
    directory_promoted_file_paths: list[str] = Field(default_factory=list)
    cluster_promoted_file_paths: list[str] = Field(default_factory=list)
    empty_service_names: list[str] = Field(default_factory=list)
    dropped_service_names: list[str] = Field(default_factory=list)

    @field_validator(
        "invented_file_paths",
        "overlap_file_paths",
        "shared_file_paths",
        "unclassified_file_paths",
        "connectivity_promoted_file_paths",
        "directory_promoted_file_paths",
        "cluster_promoted_file_paths",
    )
    @classmethod
    def normalize_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class ServiceGroupingArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    grouping_id: str
    version: ServiceGroupingVersion = ServiceGroupingVersion.V1
    template_version: ServiceTemplateVersion
    structural_graph_id: str
    repo_path: str
    known_file_paths: list[str]
    architecture_summary: str
    services: list[ServiceDefinition]
    file_assignments: list[ServiceFileAssignment]
    llm_invocation: LLMInvocationRecord
    summary: ServiceGroupingSummary
    diagnostics: ServiceGroupingDiagnostics

    @field_validator("known_file_paths")
    @classmethod
    def normalize_known_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]

    @model_validator(mode="after")
    def validate_integrity(self) -> "ServiceGroupingArtifact":
        known_file_set = set(self.known_file_paths)
        if len(known_file_set) != len(self.known_file_paths):
            raise ValidationError("Duplicate known file paths detected in service grouping artifact")

        service_ids = [service.id for service in self.services]
        if len(service_ids) != len(set(service_ids)):
            raise ValidationError("Duplicate service ids detected", context={"service_ids": service_ids})

        assignment_paths = [assignment.file_path for assignment in self.file_assignments]
        if set(assignment_paths) != known_file_set or len(assignment_paths) != len(self.known_file_paths):
            raise ValidationError(
                "Service grouping assignments must cover every known file exactly once",
                context={"known_file_count": len(self.known_file_paths), "assignment_count": len(self.file_assignments)},
            )

        assignment_by_service: dict[str, list[str]] = {}
        for assignment in self.file_assignments:
            if assignment.file_path not in known_file_set:
                raise ValidationError("Service assignment references unknown file path", context={"file_path": assignment.file_path})
            assignment_by_service.setdefault(assignment.assigned_service_id, []).append(assignment.file_path)

        if set(assignment_by_service) != set(service_ids):
            raise ValidationError(
                "Service grouping assignments reference a different service set than serialized services",
                context={"assigned_service_ids": sorted(assignment_by_service), "service_ids": sorted(service_ids)},
            )

        for service in self.services:
            member_set = set(service.member_file_paths)
            if not member_set.issubset(known_file_set):
                raise ValidationError("Service member file path is not grounded in known files", context={"service_id": service.id})
            if set(assignment_by_service.get(service.id, [])) != member_set:
                raise ValidationError("Service members do not reconcile with file assignments", context={"service_id": service.id})

        if self.summary.service_count != len(self.services):
            raise ValidationError("Summary service_count does not match serialized services")
        if self.summary.file_count != len(self.known_file_paths):
            raise ValidationError("Summary file_count does not match serialized known files")
        if self.summary.inferred_service_count != sum(1 for service in self.services if service.kind == ServiceKind.INFERRED):
            raise ValidationError("Summary inferred_service_count does not match inferred services")
        if self.summary.shared_file_count != sum(1 for item in self.file_assignments if item.assignment_kind == ServiceAssignmentKind.SHARED):
            raise ValidationError("Summary shared_file_count does not match file assignments")
        if self.summary.unclassified_file_count != sum(1 for item in self.file_assignments if item.assignment_kind == ServiceAssignmentKind.UNCLASSIFIED):
            raise ValidationError("Summary unclassified_file_count does not match file assignments")
        if self.summary.ambiguous_file_count != len(self.diagnostics.overlap_file_paths):
            raise ValidationError("Summary ambiguous_file_count does not match overlap diagnostics")
        if self.summary.invented_file_reference_count != len(self.diagnostics.invented_file_paths):
            raise ValidationError("Summary invented_file_reference_count does not match diagnostics")
        if self.summary.dropped_service_count != len(self.diagnostics.dropped_service_names):
            raise ValidationError("Summary dropped_service_count does not match diagnostics")
        return self


class ServiceGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: ServiceKind
    layer: ServiceLayer
    summary: str
    member_file_paths: list[str]
    file_count: int
    files_by_language: dict[str, int] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None

    @field_validator("member_file_paths")
    @classmethod
    def normalize_member_file_paths(cls, values: list[str]) -> list[str]:
        return [normalize_repo_path(value) for value in values]


class ServiceEdgeFilePair(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_file_path: str
    target_file_path: str

    @field_validator("source_file_path", "target_file_path")
    @classmethod
    def normalize_paths(cls, value: str) -> str:
        return normalize_repo_path(value)


class ServiceGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    target: str
    relationship_types: list[str] = Field(default_factory=list)
    supporting_structural_edge_ids: list[str] = Field(default_factory=list)
    supporting_file_pairs: list[ServiceEdgeFilePair] = Field(default_factory=list)
    supporting_edge_count: int = 0


class ServiceGraphSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_count: int
    service_edge_count: int
    file_count: int
    internal_structural_edge_count: int
    inter_service_structural_edge_count: int
    services_by_layer: dict[str, int] = Field(default_factory=dict)


class ServiceGraphDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    unmapped_structural_edge_count: int = 0


class ServiceGraphArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_graph_id: str
    version: ServiceGraphVersion = ServiceGraphVersion.V1
    grouping_id: str
    structural_graph_id: str
    repo_path: str
    nodes: list[ServiceGraphNode]
    service_edges: list[ServiceGraphEdge]
    summary: ServiceGraphSummary
    diagnostics: ServiceGraphDiagnostics

    @model_validator(mode="after")
    def validate_integrity(self) -> "ServiceGraphArtifact":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValidationError("Duplicate service graph node ids detected", context={"node_ids": node_ids})

        node_id_set = set(node_ids)
        for edge in self.service_edges:
            if edge.source not in node_id_set or edge.target not in node_id_set:
                raise ValidationError("Service graph edge references missing service node", context={"edge_id": edge.id})
            if edge.supporting_edge_count != len(edge.supporting_structural_edge_ids):
                raise ValidationError("Service graph edge supporting_edge_count does not match structural edge ids", context={"edge_id": edge.id})

        if self.summary.service_count != len(self.nodes):
            raise ValidationError("Summary service_count does not match serialized service nodes")
        if self.summary.service_edge_count != len(self.service_edges):
            raise ValidationError("Summary service_edge_count does not match serialized service edges")
        if self.summary.inter_service_structural_edge_count != sum(edge.supporting_edge_count for edge in self.service_edges):
            raise ValidationError("Summary inter_service_structural_edge_count does not reconcile with service edges")
        return self