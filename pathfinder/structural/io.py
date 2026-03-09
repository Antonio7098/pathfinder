"""Persistence helpers for structural graph artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from pathfinder.errors import PersistenceError
from pathfinder.structural.models import StructuralGraphArtifact


def write_structural_graph(artifact: StructuralGraphArtifact, output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    except Exception as exc:
        raise PersistenceError("Failed to write structural graph artifact", context={"output_path": str(output_path), "cause": str(exc)}) from exc


def read_structural_graph(input_path: Path) -> StructuralGraphArtifact:
    try:
        return StructuralGraphArtifact.model_validate_json(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PersistenceError("Failed to read structural graph artifact", context={"input_path": str(input_path), "cause": str(exc)}) from exc
