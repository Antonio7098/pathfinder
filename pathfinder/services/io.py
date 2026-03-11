"""Persistence helpers for service grouping and service graph artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from pathfinder.errors import PersistenceError
from pathfinder.services.models import ServiceGraphArtifact, ServiceGroupingArtifact


def write_service_grouping(artifact: ServiceGroupingArtifact, output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    except Exception as exc:
        raise PersistenceError("Failed to write service grouping artifact", context={"output_path": str(output_path), "cause": str(exc)}) from exc


def read_service_grouping(input_path: Path) -> ServiceGroupingArtifact:
    try:
        return ServiceGroupingArtifact.model_validate_json(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PersistenceError("Failed to read service grouping artifact", context={"input_path": str(input_path), "cause": str(exc)}) from exc


def write_service_graph(artifact: ServiceGraphArtifact, output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    except Exception as exc:
        raise PersistenceError("Failed to write service graph artifact", context={"output_path": str(output_path), "cause": str(exc)}) from exc


def read_service_graph(input_path: Path) -> ServiceGraphArtifact:
    try:
        return ServiceGraphArtifact.model_validate_json(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PersistenceError("Failed to read service graph artifact", context={"input_path": str(input_path), "cause": str(exc)}) from exc