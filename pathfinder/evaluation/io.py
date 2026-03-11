"""Persistence helpers for evaluation datasets and run artifacts."""

from __future__ import annotations

import csv
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


def write_evaluation_run_csv(artifact: EvaluationRunArtifact, output_path: Path) -> None:
    fieldnames = [
        "run_id",
        "dataset_id",
        "provider",
        "model",
        "case_type",
        "case_id",
        "subject_id",
        "file_path",
        "structural_edge_id",
        "source_path",
        "target_path",
        "relationship_type",
        "expected_risk_score",
        "expected_risk_label",
        "predicted_risk_score",
        "predicted_risk_label",
        "score_absolute_error",
        "label_match",
        "expected_high_risk",
        "predicted_high_risk",
        "high_risk_match",
        "expected_attack_edge",
        "predicted_has_attack",
        "presence_match",
        "expected_attack_types",
        "predicted_attack_types",
        "top_1_attack_type",
        "relaxed_attack_type_match",
        "exact_attack_type_match",
        "attack_type_jaccard",
        "expected_edge_attack_cost",
        "predicted_edge_attack_cost",
        "edge_attack_cost_absolute_error",
        "estimated_cost_usd",
        "invocation_duration_seconds",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "error_message",
    ]
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in _build_csv_rows(artifact):
                writer.writerow(row)
    except Exception as exc:
        raise PersistenceError("Failed to write evaluation run CSV", context={"output_path": str(output_path), "cause": str(exc)}) from exc


def _build_csv_rows(artifact: EvaluationRunArtifact) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    shared = {
        "run_id": artifact.run_id,
        "dataset_id": artifact.dataset_id,
        "provider": artifact.provider.value,
        "model": artifact.model,
    }
    for result in artifact.file_results:
        invocation = result.llm_invocation
        rows.append(
            {
                **shared,
                "case_type": "file_risk",
                "case_id": result.case_id,
                "subject_id": result.file_path,
                "file_path": result.file_path,
                "structural_edge_id": None,
                "source_path": None,
                "target_path": None,
                "relationship_type": None,
                "expected_risk_score": result.expected_risk_score,
                "expected_risk_label": result.expected_risk_label.value,
                "predicted_risk_score": result.predicted_risk_score,
                "predicted_risk_label": result.predicted_risk_label.value if result.predicted_risk_label is not None else None,
                "score_absolute_error": result.score_absolute_error,
                "label_match": result.label_match,
                "expected_high_risk": result.expected_high_risk,
                "predicted_high_risk": result.predicted_high_risk,
                "high_risk_match": result.high_risk_match,
                "expected_attack_edge": None,
                "predicted_has_attack": None,
                "presence_match": None,
                "expected_attack_types": None,
                "predicted_attack_types": None,
                "top_1_attack_type": None,
                "relaxed_attack_type_match": None,
                "exact_attack_type_match": None,
                "attack_type_jaccard": None,
                "expected_edge_attack_cost": None,
                "predicted_edge_attack_cost": None,
                "edge_attack_cost_absolute_error": None,
                "estimated_cost_usd": result.estimated_cost_usd,
                "invocation_duration_seconds": invocation.duration_seconds if invocation is not None else None,
                "input_tokens": invocation.usage.input_tokens if invocation is not None and invocation.usage is not None else None,
                "output_tokens": invocation.usage.output_tokens if invocation is not None and invocation.usage is not None else None,
                "total_tokens": invocation.usage.total_tokens if invocation is not None and invocation.usage is not None else None,
                "error_message": result.error_message,
            }
        )
    for result in artifact.attack_edge_results:
        invocation = result.llm_invocation
        rows.append(
            {
                **shared,
                "case_type": "attack_edge",
                "case_id": result.case_id,
                "subject_id": result.structural_edge_id,
                "file_path": None,
                "structural_edge_id": result.structural_edge_id,
                "source_path": result.source_path,
                "target_path": result.target_path,
                "relationship_type": result.relationship_type.value,
                "expected_risk_score": None,
                "expected_risk_label": None,
                "predicted_risk_score": None,
                "predicted_risk_label": None,
                "score_absolute_error": None,
                "label_match": None,
                "expected_high_risk": None,
                "predicted_high_risk": None,
                "high_risk_match": None,
                "expected_attack_edge": result.expected_attack_edge,
                "predicted_has_attack": result.predicted_has_attack,
                "presence_match": result.presence_match,
                "expected_attack_types": "|".join(result.expected_attack_types),
                "predicted_attack_types": "|".join(result.predicted_attack_types),
                "top_1_attack_type": result.top_1_attack_type,
                "relaxed_attack_type_match": result.relaxed_attack_type_match,
                "exact_attack_type_match": result.exact_attack_type_match,
                "attack_type_jaccard": result.attack_type_jaccard,
                "expected_edge_attack_cost": result.expected_edge_attack_cost,
                "predicted_edge_attack_cost": result.predicted_edge_attack_cost,
                "edge_attack_cost_absolute_error": result.edge_attack_cost_absolute_error,
                "estimated_cost_usd": result.estimated_cost_usd,
                "invocation_duration_seconds": invocation.duration_seconds if invocation is not None else None,
                "input_tokens": invocation.usage.input_tokens if invocation is not None and invocation.usage is not None else None,
                "output_tokens": invocation.usage.output_tokens if invocation is not None and invocation.usage is not None else None,
                "total_tokens": invocation.usage.total_tokens if invocation is not None and invocation.usage is not None else None,
                "error_message": result.error_message,
            }
        )
    return rows