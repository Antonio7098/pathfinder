"""Read-only graph adapters that expose a common downstream analysis shape."""

from __future__ import annotations

from dataclasses import dataclass

from pathfinder.errors import ValidationError
from pathfinder.reporting.enums import GraphScope
from pathfinder.services.models import ServiceGraphArtifact, ServiceGroupingArtifact
from pathfinder.structural.models import StructuralGraphArtifact


@dataclass(frozen=True, slots=True)
class AnalysisGraphNode:
    id: str
    path: str
    language: str
    display_name: str | None
    target_flag: bool
    normalized_risk_score: float | None
    confidence: float | None
    rationale: str | None
    backing_file_paths: list[str]


@dataclass(frozen=True, slots=True)
class AnalysisGraphEdge:
    id: str
    source: str
    target: str
    relationship_type: str | None
    attack_type: str | None
    edge_attack_cost: float | None
    confidence: float | None
    rationale: str | None
    structural_basis_edge_ids: list[str]


class AnalysisGraph:
    def __init__(self, *, graph_scope: GraphScope, repo_path: str, graph_id: str) -> None:
        self.graph_scope = graph_scope
        self.repo_path = repo_path
        self.graph_id = graph_id

    def node(self, node_id: str) -> AnalysisGraphNode:
        raise NotImplementedError

    def edge(self, source_id: str, target_id: str) -> AnalysisGraphEdge:
        raise NotImplementedError


class StructuralAnalysisGraph(AnalysisGraph):
    def __init__(self, artifact: StructuralGraphArtifact) -> None:
        super().__init__(graph_scope=GraphScope.FILE, repo_path=artifact.repo_path, graph_id=artifact.graph_id)
        self._node_by_id = {node.id: node for node in artifact.nodes}
        self._edge_by_pair = {(edge.source, edge.target): edge for edge in artifact.structural_edges}

    def node(self, node_id: str) -> AnalysisGraphNode:
        node = self._node_by_id.get(node_id)
        if node is None:
            raise ValidationError("Analysis graph node id is not present in structural graph", context={"node_id": node_id})
        return AnalysisGraphNode(
            id=node.id,
            path=node.path,
            language=node.language,
            display_name=None,
            target_flag=node.target_flag,
            normalized_risk_score=node.normalized_risk_score,
            confidence=node.confidence,
            rationale=node.rationale,
            backing_file_paths=[],
        )

    def edge(self, source_id: str, target_id: str) -> AnalysisGraphEdge:
        edge = self._edge_by_pair.get((source_id, target_id))
        if edge is None:
            raise ValidationError("Analysis edge is not present in structural graph", context={"source": source_id, "target": target_id})
        return AnalysisGraphEdge(
            id=edge.id,
            source=edge.source,
            target=edge.target,
            relationship_type=edge.relationship_type.value,
            attack_type=None,
            edge_attack_cost=None,
            confidence=edge.confidence,
            rationale=edge.evidence,
            structural_basis_edge_ids=[],
        )


class ServiceAnalysisGraph(AnalysisGraph):
    def __init__(self, service_graph: ServiceGraphArtifact, grouping: ServiceGroupingArtifact) -> None:
        if service_graph.grouping_id != grouping.grouping_id:
            raise ValidationError(
                "Service graph and grouping must agree before building a service analysis graph",
                context={"service_graph_grouping_id": service_graph.grouping_id, "grouping_id": grouping.grouping_id},
            )
        super().__init__(graph_scope=GraphScope.SERVICE, repo_path=service_graph.repo_path, graph_id=service_graph.service_graph_id)
        self._node_by_id = {node.id: node for node in service_graph.nodes}
        self._edge_by_pair = {(edge.source, edge.target): edge for edge in service_graph.service_edges}

    def node(self, node_id: str) -> AnalysisGraphNode:
        node = self._node_by_id.get(node_id)
        if node is None:
            raise ValidationError("Analysis graph node id is not present in service graph", context={"node_id": node_id})
        representative_path = sorted(node.member_file_paths)[0]
        return AnalysisGraphNode(
            id=node.id,
            path=representative_path,
            language=self._service_language(node.files_by_language),
            display_name=node.name,
            target_flag=False,
            normalized_risk_score=None,
            confidence=node.confidence,
            rationale=node.rationale,
            backing_file_paths=node.member_file_paths,
        )

    def edge(self, source_id: str, target_id: str) -> AnalysisGraphEdge:
        edge = self._edge_by_pair.get((source_id, target_id))
        if edge is None:
            raise ValidationError("Analysis edge is not present in service graph", context={"source": source_id, "target": target_id})
        return AnalysisGraphEdge(
            id=edge.id,
            source=edge.source,
            target=edge.target,
            relationship_type=edge.relationship_types[0] if edge.relationship_types else None,
            attack_type=None,
            edge_attack_cost=None,
            confidence=None,
            rationale=None,
            structural_basis_edge_ids=edge.supporting_structural_edge_ids,
        )

    def _service_language(self, files_by_language: dict[str, int]) -> str:
        if not files_by_language:
            return "unknown"
        if len(files_by_language) == 1:
            return next(iter(files_by_language))
        return "mixed"
