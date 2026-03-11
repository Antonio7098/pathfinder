from __future__ import annotations

import json
from pathlib import Path

from pathfinder.cli import main
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredPrompt, TokenUsage
from pathfinder.services.enums import ServiceAssignmentKind, ServiceLayer, ServiceResolutionSource, ServiceTemplateVersion
from pathfinder.services.models import ServiceDefinition, ServiceFileAssignment, ServiceGraphArtifact, ServiceGraphDiagnostics, ServiceGraphEdge, ServiceGraphNode, ServiceGraphSummary, ServiceGroupingArtifact, ServiceGroupingDiagnostics, ServiceGroupingSummary


def build_grouping_artifact(repo_path: Path) -> ServiceGroupingArtifact:
    prompt = StructuredPrompt(
        template_version="service-grouping-v1",
        prompt_version="service-grouping-prompt-v3",
        system_prompt="system",
        user_prompt="user",
        system_prompt_sha256="sys",
        user_prompt_sha256="usr",
    )
    return ServiceGroupingArtifact(
        grouping_id="sg:repo:test",
        template_version=ServiceTemplateVersion.V1,
        structural_graph_id="repo:test",
        repo_path=str(repo_path),
        known_file_paths=["web/routes.py", "pkg/service.py"],
        architecture_summary="Two service groups.",
        services=[
            ServiceDefinition(
                id="svc:web",
                name="Web",
                layer=ServiceLayer.EDGE,
                summary="Edge",
                member_file_paths=["web/routes.py"],
            ),
            ServiceDefinition(
                id="svc:app",
                name="App",
                layer=ServiceLayer.APPLICATION,
                summary="App",
                member_file_paths=["pkg/service.py"],
            ),
        ],
        file_assignments=[
            ServiceFileAssignment(file_path="web/routes.py", assigned_service_id="svc:web", assignment_kind=ServiceAssignmentKind.PRIMARY, resolution_source=ServiceResolutionSource.LLM_PRIMARY),
            ServiceFileAssignment(file_path="pkg/service.py", assigned_service_id="svc:app", assignment_kind=ServiceAssignmentKind.PRIMARY, resolution_source=ServiceResolutionSource.LLM_PRIMARY),
        ],
        llm_invocation=LLMInvocationRecord(
            provider=LLMProvider.OPENROUTER,
            base_url="https://openrouter.ai/api/v1",
            model="openrouter/test-model",
            operation_name="service_grouping.generate",
            response_format_name="LLMServiceGroupingPayload",
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
        summary=ServiceGroupingSummary(
            service_count=2,
            inferred_service_count=2,
            file_count=2,
            shared_file_count=0,
            unclassified_file_count=0,
            ambiguous_file_count=0,
            invented_file_reference_count=0,
            dropped_service_count=0,
        ),
        diagnostics=ServiceGroupingDiagnostics(prompt_file_count=2, prompt_edge_count=1, total_prompt_chars=100),
    )


def build_service_graph_artifact(repo_path: Path) -> ServiceGraphArtifact:
    return ServiceGraphArtifact(
        service_graph_id="svg:repo:test",
        grouping_id="sg:repo:test",
        structural_graph_id="repo:test",
        repo_path=str(repo_path),
        nodes=[
            ServiceGraphNode(id="svc:web", name="Web", kind="inferred", layer=ServiceLayer.EDGE, summary="Edge", member_file_paths=["web/routes.py"], file_count=1, files_by_language={"python": 1}),
            ServiceGraphNode(id="svc:app", name="App", kind="inferred", layer=ServiceLayer.APPLICATION, summary="App", member_file_paths=["pkg/service.py"], file_count=1, files_by_language={"python": 1}),
        ],
        service_edges=[
            ServiceGraphEdge(id="sve:svc:web->svc:app", source="svc:web", target="svc:app", relationship_types=["calls"], supporting_structural_edge_ids=["se:web/routes.py->pkg/service.py:calls"], supporting_edge_count=1),
        ],
        summary=ServiceGraphSummary(
            service_count=2,
            service_edge_count=1,
            file_count=2,
            internal_structural_edge_count=0,
            inter_service_structural_edge_count=1,
            services_by_layer={"application": 1, "edge": 1},
        ),
        diagnostics=ServiceGraphDiagnostics(unmapped_structural_edge_count=0),
    )


def test_cli_identify_services(monkeypatch, tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "structural_graph.json"
    raw_codegraph_path = tmp_path / "raw_codegraph.json"
    input_path.write_text("{}", encoding="utf-8")
    raw_codegraph_path.write_text("{}", encoding="utf-8")

    class FakeService:
        def run(self, request):
            assert request.input_path == input_path
            assert request.raw_codegraph_input_path == raw_codegraph_path
            return type("Result", (), {"artifact": build_grouping_artifact(tmp_path), "output_path": request.output_path, "duration_seconds": 0.1})()

    monkeypatch.setattr("pathfinder.cli.create_openrouter_service_grouping_service", lambda logger, model_override=None, timeout_seconds=60.0: FakeService())

    exit_code = main([
        "identify-services",
        "--input",
        str(input_path),
        "--raw-codegraph",
        str(raw_codegraph_path),
        "--output",
        str(tmp_path / "out.json"),
    ])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["service_count"] == 2


def test_cli_identify_services_with_minimax_provider(monkeypatch, tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "structural_graph.json"
    raw_codegraph_path = tmp_path / "raw_codegraph.json"
    input_path.write_text("{}", encoding="utf-8")
    raw_codegraph_path.write_text("{}", encoding="utf-8")

    class FakeService:
        def run(self, request):
            assert request.input_path == input_path
            assert request.raw_codegraph_input_path == raw_codegraph_path
            return type("Result", (), {"artifact": build_grouping_artifact(tmp_path), "output_path": request.output_path, "duration_seconds": 0.1})()

    monkeypatch.setattr("pathfinder.cli.create_minimax_service_grouping_service", lambda logger, model_override=None, timeout_seconds=60.0: FakeService())

    exit_code = main([
        "identify-services",
        "--input",
        str(input_path),
        "--raw-codegraph",
        str(raw_codegraph_path),
        "--output",
        str(tmp_path / "out.json"),
        "--provider",
        "minimax",
    ])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["service_count"] == 2


def test_cli_build_service_graph(monkeypatch, tmp_path: Path, capsys) -> None:
    structural_graph_path = tmp_path / "structural_graph.json"
    grouping_path = tmp_path / "grouping.json"
    structural_graph_path.write_text("{}", encoding="utf-8")
    grouping_path.write_text("{}", encoding="utf-8")

    class FakeService:
        def __init__(self, logger) -> None:
            self._logger = logger

        def run(self, request):
            assert request.structural_graph_path == structural_graph_path
            assert request.grouping_path == grouping_path
            return type("Result", (), {"artifact": build_service_graph_artifact(tmp_path), "output_path": request.output_path, "duration_seconds": 0.1})()

    monkeypatch.setattr("pathfinder.cli.ServiceGraphService", FakeService)

    exit_code = main([
        "build-service-graph",
        "--structural-graph",
        str(structural_graph_path),
        "--grouping",
        str(grouping_path),
        "--output",
        str(tmp_path / "service_graph.json"),
    ])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["service_edge_count"] == 1
