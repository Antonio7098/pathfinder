from __future__ import annotations

from pathlib import Path

from pathfinder.evaluation import PricingConfig, SecurityEvaluationRequest, SecurityEvaluationService, read_evaluation_dataset
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredPrompt, TokenUsage
from pathfinder.observability.logging import get_logger
from pathfinder.security_evaluators.models import EdgeSecurityAnalysisResult, FileSecurityAnalysisResult


def _build_invocation(operation_name: str, response_format_name: str, *, input_tokens: int, output_tokens: int, duration_seconds: float) -> LLMInvocationRecord:
    prompt = StructuredPrompt(
        template_version="test-template",
        prompt_version="test-prompt",
        system_prompt="system",
        user_prompt="user",
        system_prompt_sha256="sys",
        user_prompt_sha256="usr",
    )
    return LLMInvocationRecord(
        provider=LLMProvider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/fake-eval-model",
        operation_name=operation_name,
        response_format_name=response_format_name,
        template_version=prompt.template_version,
        prompt_version=prompt.prompt_version,
        system_prompt=prompt.system_prompt,
        user_prompt=prompt.user_prompt,
        system_prompt_sha256=prompt.system_prompt_sha256,
        user_prompt_sha256=prompt.user_prompt_sha256,
        system_prompt_chars=len(prompt.system_prompt),
        user_prompt_chars=len(prompt.user_prompt),
        provider_request_id="req_eval",
        finish_reason="stop",
        usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        duration_seconds=duration_seconds,
    )


class FakeAI:
    def __init__(self, dataset) -> None:
        self.model = "openrouter/fake-eval-model"
        self._file_cases = {case.file_path: case for case in dataset.file_risk_cases}
        self._edge_cases = {case.structural_edge_id: case for case in dataset.attack_edge_cases}

    def analyze_node_content_result(self, file_path: str, code: str) -> FileSecurityAnalysisResult:
        case = self._file_cases[file_path]
        score = case.expected_risk_score
        return FileSecurityAnalysisResult(
            node_payload={
                "tags": ["golden-match"],
                "confidence": 0.9,
                "rationale": case.rationale,
                "security_scores": {
                    "exploitability": score,
                    "privilege_gain": score,
                    "data_access_value": score,
                    "lateral_movement_value": score,
                    "detection_risk": max(0.0, 1.0 - score),
                    "confidence": 0.9,
                },
                "normalized_risk_score": score,
            },
            invocation=_build_invocation(
                "security_evaluation.file",
                "FileSecurityAnalysisPayload",
                input_tokens=100,
                output_tokens=20,
                duration_seconds=0.1,
            ),
        )

    def analyze_edge_content_result(
        self,
        *,
        structural_edge,
        source_id: str,
        target_id: str,
        source_path: str,
        target_path: str,
        source_code: str,
        target_code: str,
    ) -> EdgeSecurityAnalysisResult:
        case = self._edge_cases[structural_edge["id"]]
        attacks = []
        if case.expected_attack_edge:
            for index, attack_type in enumerate(case.expected_attack_types):
                attacks.append(
                    {
                        "id": f"ae:{case.structural_edge_id}:{attack_type}:{index}",
                        "source": source_id,
                        "target": target_id,
                        "attack_type": attack_type,
                        "transition_likelihood": 0.9,
                        "required_capability": "low",
                        "detection_risk": 0.1,
                        "edge_attack_cost": case.expected_edge_attack_cost or 0.2,
                        "confidence": 0.9,
                        "rationale": case.rationale,
                        "structural_basis_edge_ids": [case.structural_edge_id],
                        "excluded_flag": False,
                    }
                )
        return EdgeSecurityAnalysisResult(
            attack_edges=attacks,
            invocation=_build_invocation(
                "security_evaluation.edge",
                "EdgeSecurityAnalysisPayload",
                input_tokens=120,
                output_tokens=30,
                duration_seconds=0.12,
            ),
        )


def test_security_evaluation_service_runs_against_manual_dataset(tmp_path: Path) -> None:
    dataset_path = Path("tests/fixtures/security_eval/demo_vuln_repo_golden_dataset.json")
    dataset = read_evaluation_dataset(dataset_path)
    service = SecurityEvaluationService(
        get_logger("test.security_evaluation"),
        ai_factory=lambda **kwargs: FakeAI(dataset),
    )

    result = service.run(
        SecurityEvaluationRequest(
            dataset_path=dataset_path,
            output_path=tmp_path / "security_eval_run.json",
            provider=LLMProvider.OPENROUTER,
            model="openrouter/fake-eval-model",
            pricing=PricingConfig(
                input_token_price_per_1m_usd=1.0,
                output_token_price_per_1m_usd=2.0,
            ),
        )
    )

    assert result.output_path.exists()
    assert result.artifact.summary.file_risk.label_accuracy == 1.0
    assert result.artifact.summary.attack_edges.presence_f1 == 1.0
    assert result.artifact.summary.attack_edges.relaxed_attack_type_accuracy == 1.0
    assert result.artifact.summary.runtime.invocation_count == 21
    assert result.artifact.summary.runtime.total_input_tokens == (11 * 100) + (10 * 120)
    assert result.artifact.summary.runtime.total_output_tokens == (11 * 20) + (10 * 30)
    assert result.artifact.summary.runtime.estimated_total_cost_usd is not None
    assert result.artifact.diagnostics.missing_cost_case_ids == []