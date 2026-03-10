from __future__ import annotations

import json
from pathlib import Path

from pathfinder.cli import main
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredPrompt, TokenUsage
from pathfinder.reporting.enums import RecommendationPriority, RecommendationTemplateVersion
from pathfinder.reporting.input_models import PathEdgeInput, PathNodeInput, RecommendationReportInputArtifact, RecommendationReportInputSummary
from pathfinder.reporting.models import RecommendationItem, RecommendationPathOverview, RecommendationReportArtifact, RecommendationReportDiagnostics, RecommendationReportSummary


def build_artifact(repo_path: Path) -> RecommendationReportArtifact:
    prompt = StructuredPrompt(
        template_version="recommendation-report-v1",
        prompt_version="recommendation-report-prompt-v1",
        system_prompt="system",
        user_prompt="user",
        system_prompt_sha256="sys",
        user_prompt_sha256="usr",
    )
    return RecommendationReportArtifact(
        report_id="rr:path-1:recommendation-report-v1",
        template_version=RecommendationTemplateVersion.V1,
        input_artifact_id="input:path-1",
        repo_path=str(repo_path),
        known_file_paths=["web/routes.py", "pkg/service.py", "pkg/db.py"],
        path_overview=RecommendationPathOverview(
            path_id="path-1",
            ordered_node_ids=["web/routes.py", "pkg/service.py", "pkg/db.py"],
            ordered_edge_ids=["edge-1", "edge-2"],
            ordered_file_paths=["web/routes.py", "pkg/service.py", "pkg/db.py"],
            path_narrative="narrative",
            target_rationale="target",
            top_priority_file_path="web/routes.py",
            top_priority_rationale="first",
        ),
        recommendations=[
            RecommendationItem(
                id="recommendation:1",
                priority=RecommendationPriority.HIGH,
                title="Patch route",
                summary="Patch route validation",
                mitigation_steps=["Step 1"],
                primary_file_path="web/routes.py",
                supporting_file_paths=["pkg/service.py"],
                supporting_node_ids=["web/routes.py"],
                supporting_edge_ids=["edge-1"],
                confidence=0.9,
            )
        ],
        llm_invocation=LLMInvocationRecord(
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
            usage=TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            duration_seconds=0.1,
        ),
        summary=RecommendationReportSummary(
            path_node_count=3,
            path_edge_count=2,
            known_file_count=3,
            loaded_file_count=3,
            missing_file_count=0,
            truncated_file_count=0,
            dropped_file_count=0,
            recommendation_count=1,
            citation_count=4,
        ),
        diagnostics=RecommendationReportDiagnostics(total_prompt_chars=100),
    )


def test_cli_generate_recommendation_report(monkeypatch, tmp_path: Path, capsys) -> None:
    input_artifact = RecommendationReportInputArtifact(
        input_artifact_id="input:path-1",
        repo_path=str(tmp_path),
        path_id="path-1",
        path_nodes=[
            PathNodeInput(id="web/routes.py", path="web/routes.py", language="python"),
            PathNodeInput(id="pkg/service.py", path="pkg/service.py", language="python"),
            PathNodeInput(id="pkg/db.py", path="pkg/db.py", language="python"),
        ],
        path_edges=[
            PathEdgeInput(id="edge-1", source="web/routes.py", target="pkg/service.py"),
            PathEdgeInput(id="edge-2", source="pkg/service.py", target="pkg/db.py"),
        ],
        summary=RecommendationReportInputSummary(path_node_count=3, path_edge_count=2, focal_file_count=0),
    )
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(input_artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")

    class FakeService:
        def run(self, request):
            assert request.input_path == input_path
            return type("Result", (), {"artifact": build_artifact(tmp_path), "output_path": request.output_path, "duration_seconds": 0.1})()

    monkeypatch.setattr("pathfinder.cli.create_openrouter_recommendation_report_service", lambda logger, model_override=None, timeout_seconds=60.0: FakeService())

    exit_code = main([
        "generate-recommendation-report",
        "--input",
        str(input_path),
        "--output",
        str(tmp_path / "out.json"),
    ])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["recommendation_count"] == 1