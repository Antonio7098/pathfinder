"""Typed models for the raw CodeGraph runtime surface."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CodeRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str
    display: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    start_col: int | None = None
    end_col: int | None = None


class CodeGraphBlockCustom(BaseModel):
    model_config = ConfigDict(extra="ignore")

    node_class: str | None = None
    logical_key: str | None = None
    language: str | None = None
    name: str | None = None
    symbol_kind: str | None = None
    exported: bool | None = None
    coderef: CodeRef | None = None


class CodeGraphBlockMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    custom: CodeGraphBlockCustom = Field(default_factory=CodeGraphBlockCustom)


class CodeGraphEdgeTypeCustom(BaseModel):
    model_config = ConfigDict(extra="ignore")

    custom: str


class CodeGraphEdgeCustomMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    relation: str | None = None
    raw_import: str | None = None
    raw_target: str | None = None
    symbol: str | None = None


class CodeGraphEdgeMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    custom: CodeGraphEdgeCustomMetadata = Field(default_factory=CodeGraphEdgeCustomMetadata)


class CodeGraphEdge(BaseModel):
    model_config = ConfigDict(extra="ignore")

    edge_type: str | CodeGraphEdgeTypeCustom
    target: str
    metadata: CodeGraphEdgeMetadata = Field(default_factory=CodeGraphEdgeMetadata)

    @property
    def edge_name(self) -> str:
        if isinstance(self.edge_type, str):
            return self.edge_type
        return self.edge_type.custom

    @property
    def relation(self) -> str:
        return self.metadata.custom.relation or self.edge_name


class CodeGraphBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    metadata: CodeGraphBlockMetadata = Field(default_factory=CodeGraphBlockMetadata)
    edges: list[CodeGraphEdge] = Field(default_factory=list)


class CodeGraphDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    blocks: dict[str, CodeGraphBlock]
