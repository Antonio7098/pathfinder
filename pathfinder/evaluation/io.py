"""Persistence helpers for evaluation datasets and run artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from pathfinder.errors import PersistenceError
from pathfinder.evaluation.models import EvaluationDatasetArtifact, EvaluationRunArtifact


def read_evaluation_dataset(input_path: Path) -> EvaluationDatasetArtifact:
    try:
        return EvaluationDatasetArtifact.model_validate_json(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PersistenceError("Failed to read evaluation dataset artifact", context={"input_path": str(input_path), "cause": str(exc)}) from exc


def write_evaluation_run(artifact: EvaluationRunArtifact, output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    except Exception as exc:
        raise PersistenceError("Failed to write evaluation run artifact", context={"output_path": str(output_path), "cause": str(exc)}) from exc