from __future__ import annotations

from pathlib import Path

from pathfinder.evaluation.io import read_evaluation_dataset


def test_manual_golden_dataset_loads_and_reconciles() -> None:
    dataset = read_evaluation_dataset(Path("tests/fixtures/security_eval/demo_vuln_repo_golden_dataset.json"))

    assert dataset.dataset_id == "golden:demo_vuln_repo:security_eval:v1"
    assert dataset.summary.file_case_count == 11
    assert dataset.summary.attack_edge_case_count == 10
    assert dataset.summary.high_risk_file_count == 5
    assert dataset.summary.positive_attack_edge_case_count == 5
    assert dataset.attack_edge_cases[0].structural_edge_id == "se:web/routes.py->auth/session.py:calls"