from __future__ import annotations

import pytest

from pathfinder.errors import ValidationError
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredPrompt, TokenUsage
from pathfinder.reporting.enums import RecommendationPriority, RecommendationTemplateVersion
from pathfinder.reporting.input_models import PathEdgeInput, PathNodeInput, RecommendationReportInputArtifact, RecommendationReportInputSummary, ReportFileReference
from pathfinder.reporting.models import RecommendationItem, RecommendationPathOverview, RecommendationReportArtifact, RecommendationReportDiagnostics, RecommendationReportSummary


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
        usage=TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        duration_seconds=0.1,
    )


def test_input_artifact_requires_linear_path_edges() -> None:
    with pytest.raises(ValidationError):
        RecommendationReportInputArtifact(
            input_artifact_id="input-1",
            repo_path="/repo",
            path_id="path-1",
            path_nodes=[
                PathNodeInput(id="node-a", path="a.py", language="python"),
                PathNodeInput(id="node-b", path="b.py", language="python"),
            ],
            path_edges=[PathEdgeInput(id="edge-1", source="node-b", target="node-a")],
            focal_files=[ReportFileReference(path="extra.py")],
            summary=RecommendationReportInputSummary(path_node_count=2, path_edge_count=1, focal_file_count=1),
        )


def test_report_artifact_rejects_unknown_citations() -> None:
    with pytest.raises(ValidationError):
        RecommendationReportArtifact(
            report_id="report-1",
            template_version=RecommendationTemplateVersion.V1,
            input_artifact_id="input-1",
            repo_path="/repo",
            known_file_paths=["a.py", "b.py"],
            path_overview=RecommendationPathOverview(
                path_id="path-1",
                ordered_node_ids=["node-a", "node-b"],
                ordered_edge_ids=["edge-1"],
                ordered_file_paths=["a.py", "b.py"],
                path_narrative="narrative",
                target_rationale="target",
                top_priority_file_path="a.py",
                top_priority_rationale="first",
            ),
            recommendations=[
                RecommendationItem(
                    id="recommendation:1",
                    priority=RecommendationPriority.HIGH,
                    title="Patch a",
                    summary="Do something",
                    mitigation_steps=["Step 1"],
                    primary_file_path="missing.py",
                    supporting_file_paths=["a.py"],
                    supporting_node_ids=["node-a"],
                    supporting_edge_ids=["edge-1"],
                    confidence=0.8,
                )
            ],
            llm_invocation=build_invocation(),
            summary=RecommendationReportSummary(
                path_node_count=2,
                path_edge_count=1,
                known_file_count=2,
                loaded_file_count=2,
                missing_file_count=0,
                truncated_file_count=0,
                dropped_file_count=0,
                recommendation_count=1,
                citation_count=4,
            ),
            diagnostics=RecommendationReportDiagnostics(total_prompt_chars=10),
        )