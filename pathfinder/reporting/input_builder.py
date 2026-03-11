"""Deterministic recommendation-report input builders for file and service graphs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.analysis import AnalysisGraph, ServiceAnalysisGraph, StructuralAnalysisGraph
from pathfinder.errors import ValidationError
from pathfinder.observability.logging import log_event
from pathfinder.reporting.enums import GraphScope
from pathfinder.reporting.input_models import PathEdgeInput, PathNodeInput, RecommendationReportInputArtifact, RecommendationReportInputSummary, ReportFileReference
from pathfinder.reporting.io import write_recommendation_report_input
from pathfinder.services.io import read_service_graph, read_service_grouping
from pathfinder.services.models import ServiceGraphArtifact, ServiceGroupingArtifact
from pathfinder.structural.io import read_structural_graph
from pathfinder.structural.models import StructuralGraphArtifact


class RecommendationInputBuildRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    graph_scope: GraphScope = GraphScope.FILE
    structural_graph_path: Path
    output_path: Path
    path_node_ids: list[str] = Field(min_length=1)
    focal_file_paths: list[str] = Field(default_factory=list)
    path_id: str = "selected-path"
    input_artifact_id: str | None = None
    service_graph_path: Path | None = None
    grouping_path: Path | None = None


@dataclass(slots=True)
class RecommendationInputBuildResult:
    artifact: RecommendationReportInputArtifact
    output_path: Path


class RecommendationInputBuilderService:
    def __init__(self, logger) -> None:
        self._logger = logger

    def run(self, request: RecommendationInputBuildRequest) -> RecommendationInputBuildResult:
        log_event(
            self._logger,
            "recommendation_input.started",
            fields={
                "graph_scope": request.graph_scope.value,
                "structural_graph_path": str(request.structural_graph_path),
                "service_graph_path": str(request.service_graph_path) if request.service_graph_path else None,
                "grouping_path": str(request.grouping_path) if request.grouping_path else None,
                "output_path": str(request.output_path),
                "path_node_count": len(request.path_node_ids),
            },
        )
        structural_graph = read_structural_graph(request.structural_graph_path)
        if request.graph_scope == GraphScope.FILE:
            analysis_graph = StructuralAnalysisGraph(structural_graph)
            artifact = self._build_from_graph(analysis_graph=analysis_graph, request=request)
        else:
            if request.service_graph_path is None or request.grouping_path is None:
                raise ValidationError(
                    "Service-scope recommendation input requires service_graph_path and grouping_path",
                    context={"graph_scope": request.graph_scope.value},
                )
            service_graph = read_service_graph(request.service_graph_path)
            grouping = read_service_grouping(request.grouping_path)
            self._validate_service_inputs(
                structural_graph=structural_graph,
                service_graph=service_graph,
                grouping=grouping,
            )
            analysis_graph = ServiceAnalysisGraph(service_graph, grouping)
            artifact = self._build_from_graph(analysis_graph=analysis_graph, request=request)
        write_recommendation_report_input(artifact, request.output_path)
        log_event(
            self._logger,
            "recommendation_input.completed",
            fields={
                "graph_scope": artifact.graph_scope.value,
                "output_path": str(request.output_path),
                "path_id": artifact.path_id,
                "path_node_count": artifact.summary.path_node_count,
                "path_edge_count": artifact.summary.path_edge_count,
                "focal_file_count": artifact.summary.focal_file_count,
            },
        )
        return RecommendationInputBuildResult(artifact=artifact, output_path=request.output_path)

    def _validate_service_inputs(
        self,
        *,
        structural_graph: StructuralGraphArtifact,
        service_graph: ServiceGraphArtifact,
        grouping: ServiceGroupingArtifact,
    ) -> None:
        if grouping.structural_graph_id != structural_graph.graph_id:
            raise ValidationError(
                "Service grouping artifact does not match structural graph",
                context={"grouping_structural_graph_id": grouping.structural_graph_id, "structural_graph_id": structural_graph.graph_id},
            )
        if service_graph.structural_graph_id != structural_graph.graph_id or service_graph.grouping_id != grouping.grouping_id:
            raise ValidationError(
                "Service graph artifact does not match supplied structural graph/grouping",
                context={
                    "service_graph_structural_graph_id": service_graph.structural_graph_id,
                    "service_graph_grouping_id": service_graph.grouping_id,
                    "structural_graph_id": structural_graph.graph_id,
                    "grouping_id": grouping.grouping_id,
                },
            )
    def _build_from_graph(
        self,
        *,
        analysis_graph: AnalysisGraph,
        request: RecommendationInputBuildRequest,
    ) -> RecommendationReportInputArtifact:
        path_nodes: list[PathNodeInput] = []
        path_edges: list[PathEdgeInput] = []
        for node_id in request.path_node_ids:
            node = analysis_graph.node(node_id)
            path_nodes.append(
                PathNodeInput(
                    id=node.id,
                    path=node.path,
                    language=node.language,
                    display_name=node.display_name,
                    role="target" if node.target_flag else None,
                    target_flag=node.target_flag,
                    normalized_risk_score=node.normalized_risk_score,
                    confidence=node.confidence,
                    rationale=node.rationale,
                    backing_file_paths=node.backing_file_paths,
                )
            )
        for source_id, target_id in zip(request.path_node_ids, request.path_node_ids[1:]):
            edge = analysis_graph.edge(source_id, target_id)
            path_edges.append(
                PathEdgeInput(
                    id=edge.id,
                    source=edge.source,
                    target=edge.target,
                    relationship_type=edge.relationship_type,
                    attack_type=edge.attack_type,
                    edge_attack_cost=edge.edge_attack_cost,
                    confidence=edge.confidence,
                    rationale=edge.rationale,
                    structural_basis_edge_ids=edge.structural_basis_edge_ids,
                )
            )
        return self._build_artifact(
            request=request,
            repo_path=analysis_graph.repo_path,
            graph_id=analysis_graph.graph_id,
            path_nodes=path_nodes,
            path_edges=path_edges,
        )

    def _build_artifact(
        self,
        *,
        request: RecommendationInputBuildRequest,
        repo_path: str,
        graph_id: str,
        path_nodes: list[PathNodeInput],
        path_edges: list[PathEdgeInput],
    ) -> RecommendationReportInputArtifact:
        input_artifact_id = request.input_artifact_id or f"input:{request.graph_scope.value}:{request.path_id}"
        focal_files = [ReportFileReference(path=path) for path in request.focal_file_paths]
        return RecommendationReportInputArtifact(
            input_artifact_id=input_artifact_id,
            repo_path=repo_path,
            graph_scope=request.graph_scope,
            graph_id=graph_id,
            path_id=request.path_id,
            path_nodes=path_nodes,
            path_edges=path_edges,
            focal_files=focal_files,
            summary=RecommendationReportInputSummary(
                path_node_count=len(path_nodes),
                path_edge_count=len(path_edges),
                focal_file_count=len(focal_files),
            ),
        )
