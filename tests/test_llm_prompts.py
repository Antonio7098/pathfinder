from __future__ import annotations

import json

import pytest

from pathfinder.errors import ConfigurationError
from pathfinder.llm.prompts.base import build_structured_prompt
from pathfinder.llm.prompts.recommendation_report import RecommendationReportPromptContext, RecommendationReportPromptRegistry
from pathfinder.reporting.context import ReportContextBundle, ReportContextSummary, ReportFileContext
from pathfinder.reporting.enums import RecommendationTemplateVersion
from pathfinder.reporting.input_models import PathEdgeInput, PathNodeInput, RecommendationReportInputArtifact, RecommendationReportInputSummary, ReportFileReference


def build_input_artifact() -> RecommendationReportInputArtifact:
    return RecommendationReportInputArtifact(
        input_artifact_id="input:path-1",
        repo_path="/repo",
        path_id="path-1",
        path_nodes=[
            PathNodeInput(id="web/routes.py", path="web/routes.py", language="python", role="entry"),
            PathNodeInput(id="pkg/db.py", path="pkg/db.py", language="python", role="target", target_flag=True),
        ],
        path_edges=[PathEdgeInput(id="edge-1", source="web/routes.py", target="pkg/db.py", attack_type="sql_injection")],
        focal_files=[ReportFileReference(path="pkg/audit.py")],
        summary=RecommendationReportInputSummary(path_node_count=2, path_edge_count=1, focal_file_count=1),
    )


def build_context_bundle() -> ReportContextBundle:
    return ReportContextBundle(
        files=[
            ReportFileContext(path="web/routes.py", content="def route(): pass", included_char_count=17),
            ReportFileContext(path="pkg/db.py", content="def query(): pass", included_char_count=17),
        ],
        missing_file_paths=[],
        truncated_file_paths=[],
        dropped_file_paths=["pkg/audit.py"],
        summary=ReportContextSummary(
            requested_file_count=3,
            included_file_count=2,
            loaded_file_count=2,
            missing_file_count=0,
            truncated_file_count=0,
            dropped_file_count=1,
            total_prompt_chars=34,
        ),
    )


def test_build_structured_prompt_hashes_content() -> None:
    prompt = build_structured_prompt(
        template_version="template-v1",
        prompt_version="prompt-v1",
        system_prompt="system",
        user_prompt="user",
    )

    assert prompt.template_version == "template-v1"
    assert prompt.prompt_version == "prompt-v1"
    assert len(prompt.system_prompt_sha256) == 64
    assert len(prompt.user_prompt_sha256) == 64


def test_recommendation_prompt_registry_renders_versioned_prompt() -> None:
    registry = RecommendationReportPromptRegistry()
    template = registry.resolve(RecommendationTemplateVersion.V1)

    prompt = template.render(
        RecommendationReportPromptContext(
            input_artifact=build_input_artifact(),
            context_bundle=build_context_bundle(),
        )
    )

    payload = json.loads(prompt.user_prompt)
    assert prompt.template_version == "recommendation-report-v1"
    assert prompt.prompt_version == "recommendation-report-prompt-v1"
    assert payload["path_id"] == "path-1"
    assert payload["dropped_file_paths"] == ["pkg/audit.py"]
    assert payload["response_contract"]["top_priority_file_path"] == "must be one of known_file_paths"


def test_recommendation_prompt_registry_rejects_unknown_version() -> None:
    registry = RecommendationReportPromptRegistry()

    with pytest.raises(ConfigurationError):
        registry.resolve("missing-version")