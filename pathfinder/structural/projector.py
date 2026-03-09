"""Projection from CodeGraph document blocks to a structural file graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from pathfinder.adapters.codegraph_models import CodeGraphBlock, CodeGraphDocument, CodeGraphEdge
from pathfinder.errors import InternalInvariantError, ProjectionError
from pathfinder.observability.logging import log_event
from pathfinder.structural.enums import RelationshipType
from pathfinder.structural.ids import graph_id_for_repo, normalize_repo_path, structural_edge_id
from pathfinder.structural.models import FileNode, GraphSummary, ProjectionDiagnostics, StructuralEdge, StructuralEvidence, StructuralGraphArtifact


LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


@dataclass(slots=True)
class EdgeAccumulator:
    source: str
    target: str
    relationship_type: RelationshipType
    evidence_relations: set[str] = field(default_factory=set)
    provenance: list[StructuralEvidence] = field(default_factory=list)
    provenance_keys: set[tuple[str, ...]] = field(default_factory=set)


class StructuralGraphProjector:
    def __init__(self, logger) -> None:
        self._logger = logger

    def project(self, document: CodeGraphDocument, *, repo_path: Path) -> StructuralGraphArtifact:
        file_blocks = self._collect_blocks(document, expected_node_class="file")
        symbol_blocks = self._collect_blocks(document, expected_node_class="symbol")
        if not file_blocks:
            raise ProjectionError("No file nodes were found in the CodeGraph document", context={"repo_path": str(repo_path)})

        file_id_by_block = {block_id: self._path_for_block(block) for block_id, block in file_blocks.items()}
        symbol_path_by_block = {block_id: self._path_for_block(block) for block_id, block in symbol_blocks.items()}

        accumulators: dict[tuple[str, str, RelationshipType], EdgeAccumulator] = {}
        candidate_relation_count = 0
        deduplicated_evidence_count = 0
        dropped_self_edges = 0
        dropped_missing_targets = 0
        omitted_relations: dict[str, int] = {}

        for source_block_id, block in document.blocks.items():
            node_class = block.metadata.custom.node_class
            if node_class not in {"file", "symbol"}:
                continue

            source_path = file_id_by_block.get(source_block_id) or symbol_path_by_block.get(source_block_id)
            if source_path is None:
                raise InternalInvariantError("Source block is missing a stable file path", context={"source_block_id": source_block_id})

            for edge in block.edges:
                candidate_relation_count += 1
                relationship_type = self._map_relationship(node_class=node_class, edge=edge)
                if relationship_type is None:
                    omitted_relations[edge.relation] = omitted_relations.get(edge.relation, 0) + 1
                    continue

                target_block_id = self._normalize_block_id(edge.target)
                target_path = file_id_by_block.get(target_block_id) or symbol_path_by_block.get(target_block_id)
                if target_path is None:
                    dropped_missing_targets += 1
                    continue

                if source_path == target_path:
                    dropped_self_edges += 1
                    continue

                evidence = self._build_evidence(
                    source_block_id=source_block_id,
                    source_block=block,
                    target_block_id=target_block_id,
                    target_block=document.blocks.get(target_block_id),
                    edge=edge,
                )
                accumulator = accumulators.setdefault(
                    (source_path, target_path, relationship_type),
                    EdgeAccumulator(source=source_path, target=target_path, relationship_type=relationship_type),
                )
                accumulator.evidence_relations.add(edge.relation)
                evidence_key = (
                    evidence.raw_relation,
                    evidence.source_symbol or "",
                    evidence.target_symbol or "",
                    evidence.raw_import or "",
                    evidence.raw_target or "",
                )
                if evidence_key in accumulator.provenance_keys:
                    deduplicated_evidence_count += 1
                    continue
                accumulator.provenance_keys.add(evidence_key)
                accumulator.provenance.append(evidence)

        edges = self._materialize_edges(accumulators)
        nodes = self._materialize_nodes(file_blocks=file_blocks, edges=edges)
        diagnostics = ProjectionDiagnostics(
            candidate_relation_count=candidate_relation_count,
            emitted_edge_count=len(edges),
            deduplicated_evidence_count=deduplicated_evidence_count,
            dropped_self_edges=dropped_self_edges,
            dropped_missing_targets=dropped_missing_targets,
            omitted_relations=dict(sorted(omitted_relations.items())),
        )
        summary = GraphSummary(
            file_count=len(nodes),
            structural_edge_count=len(edges),
            attack_edge_count=0,
            evidence_count=sum(edge.evidence_count for edge in edges),
            files_by_language=self._summarize_languages(nodes),
            edges_by_relationship_type=self._summarize_relationships(edges),
        )
        artifact = StructuralGraphArtifact(
            graph_id=graph_id_for_repo(repo_path.name),
            repo_path=str(repo_path),
            nodes=nodes,
            structural_edges=edges,
            summary=summary,
            diagnostics=diagnostics,
        )
        log_event(
            self._logger,
            "structural_graph.projected",
            fields={
                "repo_path": str(repo_path),
                "file_count": summary.file_count,
                "structural_edge_count": summary.structural_edge_count,
                "candidate_relation_count": diagnostics.candidate_relation_count,
                "dropped_self_edges": diagnostics.dropped_self_edges,
            },
        )
        return artifact

    def _collect_blocks(self, document: CodeGraphDocument, *, expected_node_class: str) -> dict[str, CodeGraphBlock]:
        return {
            block_id: block
            for block_id, block in document.blocks.items()
            if block.metadata.custom.node_class == expected_node_class
        }

    def _materialize_nodes(self, *, file_blocks: dict[str, CodeGraphBlock], edges: list[StructuralEdge]) -> list[FileNode]:
        in_degree: dict[str, int] = {}
        out_degree: dict[str, int] = {}
        import_count: dict[str, int] = {}
        for edge in edges:
            out_degree[edge.source] = out_degree.get(edge.source, 0) + 1
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1
            if edge.relationship_type == RelationshipType.IMPORTS:
                import_count[edge.source] = import_count.get(edge.source, 0) + 1

        nodes: list[FileNode] = []
        for block in sorted(file_blocks.values(), key=lambda item: self._path_for_block(item)):
            path = self._path_for_block(block)
            nodes.append(
                FileNode(
                    id=path,
                    path=path,
                    language=self._language_for_block(block),
                    import_count=import_count.get(path, 0),
                    in_degree_structural=in_degree.get(path, 0),
                    out_degree_structural=out_degree.get(path, 0),
                )
            )
        return nodes

    def _materialize_edges(self, accumulators: dict[tuple[str, str, RelationshipType], EdgeAccumulator]) -> list[StructuralEdge]:
        edges: list[StructuralEdge] = []
        for key in sorted(accumulators, key=lambda item: (item[0], item[1], item[2].value)):
            accumulator = accumulators[key]
            provenance = sorted(
                accumulator.provenance,
                key=lambda item: (item.raw_relation, item.source_symbol or "", item.target_symbol or "", item.raw_import or "", item.raw_target or ""),
            )
            edges.append(
                StructuralEdge(
                    id=structural_edge_id(accumulator.source, accumulator.target, accumulator.relationship_type),
                    source=accumulator.source,
                    target=accumulator.target,
                    relationship_type=accumulator.relationship_type,
                    evidence=self._describe_edge(accumulator.source, accumulator.target, accumulator.relationship_type, provenance),
                    evidence_relations=sorted(accumulator.evidence_relations),
                    evidence_count=len(provenance),
                    provenance=provenance,
                )
            )
        return edges

    def _build_evidence(
        self,
        *,
        source_block_id: str,
        source_block: CodeGraphBlock,
        target_block_id: str,
        target_block: CodeGraphBlock | None,
        edge: CodeGraphEdge,
    ) -> StructuralEvidence:
        return StructuralEvidence(
            raw_relation=edge.relation,
            source_block_id=source_block_id,
            target_block_id=target_block_id,
            source_logical_key=source_block.metadata.custom.logical_key,
            target_logical_key=target_block.metadata.custom.logical_key if target_block else None,
            source_symbol=source_block.metadata.custom.name,
            target_symbol=target_block.metadata.custom.name if target_block else None,
            raw_import=edge.metadata.custom.raw_import,
            raw_target=edge.metadata.custom.raw_target,
        )

    def _map_relationship(self, *, node_class: str, edge: CodeGraphEdge) -> RelationshipType | None:
        relation = edge.relation
        if node_class == "file" and relation in {"imports", "imports_symbol", "reexports"}:
            return RelationshipType.IMPORTS
        if node_class == "file" and relation == "references":
            return RelationshipType.REFERENCES
        if node_class == "file" and relation == "includes":
            return RelationshipType.INCLUDES
        if node_class == "symbol" and relation == "uses_symbol":
            return RelationshipType.CALLS
        if node_class == "symbol" and relation in {"extends", "implements"}:
            return RelationshipType.REFERENCES
        return None

    def _path_for_block(self, block: CodeGraphBlock) -> str:
        coderef = block.metadata.custom.coderef
        if coderef is None or not coderef.path:
            logical_key = block.metadata.custom.logical_key or ""
            if logical_key.startswith("file:"):
                return normalize_repo_path(logical_key.removeprefix("file:"))
            if logical_key.startswith("symbol:") and "::" in logical_key:
                return normalize_repo_path(logical_key.removeprefix("symbol:").split("::", 1)[0])
            raise ProjectionError("Block is missing coderef.path and logical key fallback", context={"logical_key": logical_key})
        return normalize_repo_path(coderef.path)

    def _language_for_block(self, block: CodeGraphBlock) -> str:
        if block.metadata.custom.language:
            return block.metadata.custom.language
        suffix = Path(self._path_for_block(block)).suffix
        if suffix in LANGUAGE_BY_SUFFIX:
            return LANGUAGE_BY_SUFFIX[suffix]
        raise ProjectionError("Unable to determine language for file block", context={"path": self._path_for_block(block)})

    def _normalize_block_id(self, block_id: str) -> str:
        return block_id if block_id.startswith("blk_") else f"blk_{block_id}"

    def _summarize_languages(self, nodes: list[FileNode]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in nodes:
            counts[node.language] = counts.get(node.language, 0) + 1
        return dict(sorted(counts.items()))

    def _summarize_relationships(self, edges: list[StructuralEdge]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for edge in edges:
            key = edge.relationship_type.value
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def _describe_edge(
        self,
        source: str,
        target: str,
        relationship_type: RelationshipType,
        provenance: list[StructuralEvidence],
    ) -> str:
        first = provenance[0]
        detail = first.target_symbol or first.raw_import or first.raw_target or target
        return f"{source} {relationship_type.value} {target} via {first.raw_relation} ({detail})"
