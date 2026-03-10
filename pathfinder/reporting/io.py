"""Persistence helpers for recommendation report artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from pathfinder.errors import PersistenceError
from pathfinder.reporting.input_models import RecommendationReportInputArtifact
from pathfinder.reporting.models import RecommendationReportArtifact


def read_recommendation_report_input(input_path: Path) -> RecommendationReportInputArtifact:
    try:
        return RecommendationReportInputArtifact.model_validate_json(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PersistenceError("Failed to read recommendation report input artifact", context={"input_path": str(input_path), "cause": str(exc)}) from exc


def write_recommendation_report(artifact: RecommendationReportArtifact, output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    except Exception as exc:
        raise PersistenceError("Failed to write recommendation report artifact", context={"output_path": str(output_path), "cause": str(exc)}) from exc


def read_recommendation_report(output_path: Path) -> RecommendationReportArtifact:
    try:
        return RecommendationReportArtifact.model_validate_json(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PersistenceError("Failed to read recommendation report artifact", context={"output_path": str(output_path), "cause": str(exc)}) from exc