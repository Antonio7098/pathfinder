"""Stable identifier helpers for structural graph artifacts."""

from __future__ import annotations

from pathlib import PurePosixPath

from pathfinder.structural.enums import RelationshipType


def normalize_repo_path(path: str) -> str:
    normalized = PurePosixPath(path).as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def structural_edge_id(source: str, target: str, relationship_type: RelationshipType) -> str:
    return f"se:{source}->{target}:{relationship_type.value}"


def graph_id_for_repo(repo_name: str) -> str:
    return f"repo:{repo_name}"
