from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from pathfinder.errors import ValidationError
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredLLMResult, StructuredPrompt, TokenUsage
from pathfinder.observability.logging import get_logger
from pathfinder.reporting.context import ReportContextBuilder
from pathfinder.reporting.enums import RecommendationPriority, RecommendationTemplateVersion
from pathfinder.reporting.input_models import PathEdgeInput, PathNodeInput, RecommendationReportInputArtifact, RecommendationReportInputSummary, ReportFileReference
from pathfinder.reporting.io import read_recommendation_report
from pathfinder.reporting.models import LLMRecommendationItem, LLMRecommendationReportPayload
from pathfinder.reporting.service import RecommendationReportRequest, RecommendationReportResult, RecommendationReportService


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def build_input_artifact(repo_path: Path) -> RecommendationReportInputArtifact:
    return RecommendationReportInputArtifact(
        input_artifact_id="input:path-1",
        repo_path=str(repo_path),
        graph_id="repo:python_repo",
        path_id="path-1",
        path_nodes=[
            PathNodeInput(id="web/routes.py", path="web/routes.py", language="python", role="entry", confidence=0.8),
            PathNodeInput(id="pkg/service.py", path="pkg/service.py", language="python", role="transition", confidence=0.8),
            PathNodeInput(id="pkg/db.py", path="pkg/db.py", language="python", role="target", target_flag=True, normalized_risk_score=0.9),
        ],
        path_edges=[
            PathEdgeInput(id="edge-1", source="web/routes.py", target="pkg/service.py", relationship_type="calls", attack_type="broken_authentication", edge_attack_cost=0.3),
            PathEdgeInput(id="edge-2", source="pkg/service.py", target="pkg/db.py", relationship_type="calls", attack_type="unsafe_database_access", edge_attack_cost=0.2),
        ],
        focal_files=[ReportFileReference(path="pkg/audit.py"), ReportFileReference(path="pkg/missing.py")],
        summary=RecommendationReportInputSummary(path_node_count=3, path_edge_count=2, focal_file_count=2),
    )


def build_invocation() -> LLMInvocationRecord:
    prompt = StructuredPrompt(
        template_version="recommendation-report-v1",
        prompt_version="recommendation-report-prompt-v1",
        system_prompt="system",
        user_prompt="user",
        system_prompt_sha256="sys",
        user_prompt_sha256="usr",
    )
    return LLMInvocationRecord(
        provider=LLMProvider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/test-model",
        operation_name="recommendation_report.generate",
        response_format_name="LLMRecommendationReportPayload",
        template_version=prompt.template_version,
        prompt_version=prompt.prompt_version,
        system_prompt=prompt.system_prompt,
        user_prompt=prompt.user_prompt,
        system_prompt_sha256=prompt.system_prompt_sha256,
        user_prompt_sha256=prompt.user_prompt_sha256,
        system_prompt_chars=len(prompt.system_prompt),
        user_prompt_chars=len(prompt.user_prompt),
        provider_request_id="req_1",
        finish_reason="stop",
        usage=TokenUsage(input_tokens=10, output_tokens=12, total_tokens=22),
        duration_seconds=0.25,
    )


@dataclass
class FakeLLMClient:
    payload: LLMRecommendationReportPayload

    def generate(self, request, *, response_model):
        assert response_model is LLMRecommendationReportPayload
        assert request.prompt.template_version == RecommendationTemplateVersion.V1.value
        return StructuredLLMResult(parsed_output=self.payload, invocation=build_invocation())


class FailingMiniMaxClient:
    class _Config:
        base_url = "https://api.minimax.io/v1/text/chatcompletion_v2"

    _config = _Config()

    def generate(self, request, *, response_model):
        raise ValidationError(
            "Structured LLM response did not contain content",
            context={"provider_request_id": "minimax-empty"},
        )


def test_context_builder_tracks_truncation_and_dropped_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    shutil.copytree(FIXTURES / "python_repo", repo_path)
    (repo_path / "pkg" / "audit.py").write_text("print('audit')\n" * 20, encoding="utf-8")
    input_artifact = build_input_artifact(repo_path)

    bundle = ReportContextBuilder(get_logger("reporting-test")).build(
        input_artifact,
        max_files=4,
        max_file_chars=20,
    )

    assert [item.path for item in bundle.files] == ["web/routes.py", "pkg/service.py", "pkg/db.py", "pkg/audit.py"]
    assert bundle.summary.loaded_file_count == 4
    assert bundle.summary.truncated_file_count >= 1
    assert bundle.summary.dropped_file_count == 1
    assert bundle.dropped_file_paths == ["pkg/missing.py"]


def test_recommendation_service_writes_valid_report(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    shutil.copytree(FIXTURES / "python_repo", repo_path)
    (repo_path / "pkg" / "audit.py").write_text("print('audit')\n" * 20, encoding="utf-8")
    input_artifact = build_input_artifact(repo_path)
    input_path = tmp_path / "recommendation_input.json"
    input_path.write_text(json.dumps(input_artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    output_path = tmp_path / "recommendation_report.json"

    service = RecommendationReportService(
        get_logger("reporting-test"),
        llm_client=FakeLLMClient(
            LLMRecommendationReportPayload(
                path_narrative="The path moves from route handling into service logic and then into the database layer.",
                target_rationale="The database file can expose high-value data and durable compromise opportunities.",
                top_priority_file_path="web/routes.py",
                top_priority_rationale="The entry-side route is the earliest defensive choke point on the selected path.",
                recommendations=[
                    LLMRecommendationItem(
                        priority=RecommendationPriority.CRITICAL,
                        title="Harden route validation",
                        summary="Tighten validation and auth checks before service calls.",
                        mitigation_steps=["Validate request input", "Enforce route-level authz"],
                        primary_file_path="web/routes.py",
                        supporting_file_paths=["pkg/service.py"],
                        supporting_node_ids=["web/routes.py", "pkg/service.py"],
                        supporting_edge_ids=["edge-1"],
                        confidence=0.91,
                    ),
                    LLMRecommendationItem(
                        priority=RecommendationPriority.HIGH,
                        title="Add DB access guardrails",
                        summary="Constrain how service logic reaches the database layer.",
                        mitigation_steps=["Review query boundaries", "Add defensive tests around db access"],
                        primary_file_path="pkg/db.py",
                        supporting_file_paths=["pkg/service.py"],
                        supporting_node_ids=["pkg/service.py", "pkg/db.py"],
                        supporting_edge_ids=["edge-2"],
                        confidence=0.82,
                    ),
                ],
            )
        ),
        model="openrouter/test-model",
    )

    result = service.run(
        RecommendationReportRequest(
            input_path=input_path,
            output_path=output_path,
            max_files=4,
            max_file_chars=20,
        )
    )

    artifact = read_recommendation_report(output_path)
    assert result.output_path.exists()
    assert artifact.report_id == "rr:path-1:recommendation-report-v1"
    assert artifact.summary.recommendation_count == 2
    assert artifact.summary.known_file_count == 5
    assert artifact.summary.loaded_file_count == 4
    assert artifact.summary.dropped_file_count == 1
    assert artifact.path_overview.top_priority_file_path == "web/routes.py"
    assert artifact.llm_invocation.model == "openrouter/test-model"


def test_recommendation_service_rejects_unknown_citations(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    shutil.copytree(FIXTURES / "python_repo", repo_path)
    (repo_path / "pkg" / "audit.py").write_text("print('audit')\n", encoding="utf-8")
    input_artifact = build_input_artifact(repo_path)
    input_path = tmp_path / "recommendation_input.json"
    input_path.write_text(json.dumps(input_artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")

    service = RecommendationReportService(
        get_logger("reporting-test"),
        llm_client=FakeLLMClient(
            LLMRecommendationReportPayload(
                path_narrative="Narrative",
                target_rationale="Target rationale",
                top_priority_file_path="web/routes.py",
                top_priority_rationale="Because it is first",
                recommendations=[
                    LLMRecommendationItem(
                        priority=RecommendationPriority.CRITICAL,
                        title="Bad citation",
                        summary="This should fail",
                        mitigation_steps=["Step 1"],
                        primary_file_path="not_real.py",
                        confidence=0.5,
                    )
                ],
            )
        ),
        model="openrouter/test-model",
    )

    with pytest.raises(ValidationError):
        service.run(RecommendationReportRequest(input_path=input_path, output_path=tmp_path / "out.json"))


def test_recommendation_service_falls_back_for_minimax_empty_response(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    shutil.copytree(FIXTURES / "python_repo", repo_path)
    (repo_path / "pkg" / "audit.py").write_text("print('audit')\n", encoding="utf-8")
    input_artifact = build_input_artifact(repo_path)
    input_path = tmp_path / "recommendation_input.json"
    input_path.write_text(json.dumps(input_artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    output_path = tmp_path / "recommendation_report.json"

    service = RecommendationReportService(
        get_logger("reporting-test"),
        llm_client=FailingMiniMaxClient(),
        model="MiniMax-M2.5",
        provider=LLMProvider.MINIMAX,
    )

    result = service.run(
        RecommendationReportRequest(
            input_path=input_path,
            output_path=output_path,
            max_files=4,
            max_file_chars=20,
        )
    )

    artifact = read_recommendation_report(output_path)
    assert result.output_path.exists()
    assert artifact.llm_invocation.provider == LLMProvider.MINIMAX
    assert artifact.llm_invocation.finish_reason == "fallback"
    assert artifact.llm_invocation.provider_request_id == "minimax-empty"
    assert artifact.summary.recommendation_count >= 1
    assert artifact.path_overview.top_priority_file_path in artifact.known_file_paths
