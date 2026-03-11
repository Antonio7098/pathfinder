"""Deterministic derivation of service graphs from file-level structural edges."""

from __future__ import annotations

from dataclasses import dataclass, field

from pathfinder.errors import ValidationError
from pathfinder.services.enums import ServiceLayer
from pathfinder.services.ids import service_edge_id, service_graph_id_for_graph
from pathfinder.services.models import ServiceEdgeFilePair, ServiceGraphArtifact, ServiceGraphDiagnostics, ServiceGraphEdge, ServiceGraphNode, ServiceGraphSummary, ServiceGroupingArtifact
from pathfinder.structural.models import StructuralGraphArtifact


@dataclass(slots=True)
class _EdgeAccumulator:
    source: str
    target: str
    relationship_types: set[str] = field(default_factory=set)
    structural_edge_ids: list[str] = field(default_factory=list)
    file_pairs: set[tuple[str, str]] = field(default_factory=set)


class ServiceGraphBuilder:
    def build(self, *, structural_graph: StructuralGraphArtifact, grouping_artifact: ServiceGroupingArtifact) -> ServiceGraphArtifact:
        if grouping_artifact.structural_graph_id != structural_graph.graph_id:
            raise ValidationError(
                "Service grouping artifact does not match the provided structural graph",
                context={"grouping_structural_graph_id": grouping_artifact.structural_graph_id, "structural_graph_id": structural_graph.graph_id},
            )
        if grouping_artifact.repo_path != structural_graph.repo_path:
            raise ValidationError(
                "Service grouping artifact repo_path does not match the provided structural graph",
                context={"grouping_repo_path": grouping_artifact.repo_path, "structural_repo_path": structural_graph.repo_path},
            )
        assignment_by_file = {assignment.file_path: assignment.assigned_service_id for assignment in grouping_artifact.file_assignments}
        file_nodes_by_path = {node.path: node for node in structural_graph.nodes}
        nodes = [self._build_node(item, file_nodes_by_path) for item in grouping_artifact.services]

        accumulators: dict[tuple[str, str], _EdgeAccumulator] = {}
        internal_structural_edge_count = 0
        unmapped_structural_edge_count = 0

        for edge in structural_graph.structural_edges:
            source_service = assignment_by_file.get(edge.source)
            target_service = assignment_by_file.get(edge.target)
            if source_service is None or target_service is None:
                unmapped_structural_edge_count += 1
                continue
            if source_service == target_service:
                internal_structural_edge_count += 1
                continue
            accumulator = accumulators.setdefault((source_service, target_service), _EdgeAccumulator(source=source_service, target=target_service))
            accumulator.relationship_types.add(edge.relationship_type.value)
            accumulator.structural_edge_ids.append(edge.id)
            accumulator.file_pairs.add((edge.source, edge.target))

        service_edges: list[ServiceGraphEdge] = []
        for key in sorted(accumulators):
            accumulator = accumulators[key]
            service_edges.append(
                ServiceGraphEdge(
                    id=service_edge_id(accumulator.source, accumulator.target),
                    source=accumulator.source,
                    target=accumulator.target,
                    relationship_types=sorted(accumulator.relationship_types),
                    supporting_structural_edge_ids=sorted(accumulator.structural_edge_ids),
                    supporting_file_pairs=[
                        ServiceEdgeFilePair(source_file_path=source, target_file_path=target)
                        for source, target in sorted(accumulator.file_pairs)
                    ],
                    supporting_edge_count=len(accumulator.structural_edge_ids),
                )
            )

        return ServiceGraphArtifact(
            service_graph_id=service_graph_id_for_graph(structural_graph.graph_id),
            grouping_id=grouping_artifact.grouping_id,
            structural_graph_id=structural_graph.graph_id,
            repo_path=structural_graph.repo_path,
            nodes=nodes,
            service_edges=service_edges,
            summary=ServiceGraphSummary(
                service_count=len(nodes),
                service_edge_count=len(service_edges),
                file_count=len(grouping_artifact.known_file_paths),
                internal_structural_edge_count=internal_structural_edge_count,
                inter_service_structural_edge_count=sum(edge.supporting_edge_count for edge in service_edges),
                services_by_layer=self._summarize_layers(nodes),
            ),
            diagnostics=ServiceGraphDiagnostics(unmapped_structural_edge_count=unmapped_structural_edge_count),
        )

    def _build_node(self, service, file_nodes_by_path: dict[str, object]) -> ServiceGraphNode:
        files_by_language: dict[str, int] = {}
        for path in service.member_file_paths:
            node = file_nodes_by_path[path]
            files_by_language[node.language] = files_by_language.get(node.language, 0) + 1
        return ServiceGraphNode(
            id=service.id,
            name=service.name,
            kind=service.kind,
            layer=service.layer,
            summary=service.summary,
            member_file_paths=service.member_file_paths,
            file_count=len(service.member_file_paths),
            files_by_language=dict(sorted(files_by_language.items())),
            confidence=service.confidence,
            rationale=service.rationale,
        )

    def _summarize_layers(self, nodes: list[ServiceGraphNode]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in nodes:
            key = node.layer.value if isinstance(node.layer, ServiceLayer) else str(node.layer)
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))