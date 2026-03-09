"""Pydantic models for Pathfinder structural graph artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pathfinder.errors import ValidationError
from pathfinder.structural.enums import EdgeType, GraphVersion, NodeType, RelationshipType


class StructuralEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_relation: str
    extractor: str = "codegraph"
    source_block_id: str
    target_block_id: str
    source_logical_key: str | None = None
    target_logical_key: str | None = None
    source_symbol: str | None = None
    target_symbol: str | None = None
    raw_import: str | None = None
    raw_target: str | None = None


class FileNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    path: str
    language: str
    node_type: NodeType = NodeType.FILE
    entrypoint_flag: bool = False
    target_flag: bool = False
    import_count: int = 0
    in_degree_structural: int = 0
    out_degree_structural: int = 0
    tags: list[str] = Field(default_factory=list)
    normalized_risk_score: float | None = None
    confidence: float | None = None
    rationale: str | None = None


class StructuralEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    edge_type: EdgeType = EdgeType.STRUCTURAL
    source: str
    target: str
    relationship_type: RelationshipType
    structural_basis: str = "codegraph_projection"
    evidence: str | None = None
    extractor: str = "codegraph"
    confidence: float = 1.0
    evidence_relations: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    provenance: list[StructuralEvidence] = Field(default_factory=list)


class AttackTransitionEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    edge_type: EdgeType = EdgeType.ATTACK_TRANSITION
    source: str
    target: str
    attack_type: str
    structural_basis_edge_ids: list[str]
    edge_attack_cost: float


class ProjectionDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_relation_count: int = 0
    emitted_edge_count: int = 0
    deduplicated_evidence_count: int = 0
    dropped_self_edges: int = 0
    dropped_missing_targets: int = 0
    omitted_relations: dict[str, int] = Field(default_factory=dict)


class GraphSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    file_count: int
    structural_edge_count: int
    attack_edge_count: int = 0
    evidence_count: int
    files_by_language: dict[str, int] = Field(default_factory=dict)
    edges_by_relationship_type: dict[str, int] = Field(default_factory=dict)


class StructuralGraphArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    graph_id: str
    version: GraphVersion = GraphVersion.MVP_V1
    repo_path: str
    nodes: list[FileNode]
    structural_edges: list[StructuralEdge]
    attack_edges: list[AttackTransitionEdge] = Field(default_factory=list)
    summary: GraphSummary
    diagnostics: ProjectionDiagnostics

    @model_validator(mode="after")
    def validate_integrity(self) -> "StructuralGraphArtifact":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValidationError("Duplicate file node ids detected", context={"node_ids": node_ids})

        node_id_set = set(node_ids)
        for edge in self.structural_edges:
            if edge.source not in node_id_set or edge.target not in node_id_set:
                raise ValidationError(
                    "Structural edge references missing file node",
                    context={"edge_id": edge.id, "source": edge.source, "target": edge.target},
                )

        if self.summary.file_count != len(self.nodes):
            raise ValidationError("Summary file_count does not match serialized nodes", context={"expected": len(self.nodes), "actual": self.summary.file_count})
        if self.summary.structural_edge_count != len(self.structural_edges):
            raise ValidationError(
                "Summary structural_edge_count does not match serialized edges",
                context={"expected": len(self.structural_edges), "actual": self.summary.structural_edge_count},
            )
        return self
