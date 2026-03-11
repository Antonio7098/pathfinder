from __future__ import annotations

import json
from pathlib import Path

from pathfinder.cli import main
from pathfinder.evaluation.models import (
    AttackEdgeMetrics,
    EvaluationRunArtifact,
    EvaluationRunDiagnostics,
    EvaluationRunSummary,
    FileRiskMetrics,
    RuntimeMetrics,
)
from pathfinder.evaluation.service import SecurityEvaluationResult
from pathfinder.llm.models import LLMProvider


def test_cli_run_security_eval(monkeypatch, tmp_path: Path, capsys) -> None:
    class FakeService:
        def __init__(self, logger) -> None:
            self._logger = logger

        def run(self, request):
            assert request.dataset_path == tmp_path / "dataset.json"
            assert request.output_path == tmp_path / "out.json"
            assert request.csv_output_path is None
            return SecurityEvaluationResult(
                artifact=EvaluationRunArtifact(
                    run_id="eval:test:openrouter:fake",
                    dataset_id="golden:test",
                    repo_path=str(tmp_path / "repo"),
                    provider=LLMProvider.OPENROUTER,
                    model="openrouter/fake",
                    file_results=[],
                    attack_edge_results=[],
                    summary=EvaluationRunSummary(
                        total_case_count=0,
                        completed_case_count=0,
                        error_case_count=0,
                        file_case_count=0,
                        attack_edge_case_count=0,
                        risk_threshold=0.5,
                        runtime=RuntimeMetrics(invocation_count=0),
                        file_risk=FileRiskMetrics(case_count=0, completed_case_count=0, error_case_count=0),
                        attack_edges=AttackEdgeMetrics(case_count=0, completed_case_count=0, error_case_count=0, positive_case_count=0, predicted_positive_count=0),
                    ),
                    diagnostics=EvaluationRunDiagnostics(),
                ),
                output_path=request.output_path,
                csv_output_path=tmp_path / "out.csv",
                duration_seconds=0.1,
            )

    monkeypatch.setattr("pathfinder.cli.SecurityEvaluationService", FakeService)

    exit_code = main(
        [
            "run-security-eval",
            "--dataset",
            str(tmp_path / "dataset.json"),
            "--output",
            str(tmp_path / "out.json"),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["run_id"] == "eval:test:openrouter:fake"
    assert payload["output_path"].endswith("out.json")
    assert payload["csv_output_path"].endswith("out.csv")