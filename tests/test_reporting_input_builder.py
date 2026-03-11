from __future__ import annotations

import json
from pathlib import Path

from pathfinder.cli import main
from pathfinder.observability.logging import get_logger
from pathfinder.reporting.enums import GraphScope
from pathfinder.reporting.input_builder import RecommendationInputBuildRequest, RecommendationInputBuilderService
from pathfinder.reporting.io import read_recommendation_report_input
from pathfinder.services.enums import ServiceAssignmentKind, ServiceLayer, ServiceResolutionSource, ServiceTemplateVersion
from pathfinder.services.models import ServiceDefinition, ServiceFileAssignment, ServiceGroupingArtifact, ServiceGroupingDiagnostics, ServiceGroupingSummary
from pathfinder.structural.enums import RelationshipType
from pathfinder.structural.models import FileNode, GraphSummary, ProjectionDiagnostics, StructuralEdge, StructuralGraphArtifact


def build_structural_artifact(repo_path: Path) -> StructuralGraphArtifact:
    return StructuralGraphArtifact(
        graph_id="repo:python_repo",
        repo_path=str(repo_path),
        nodes=[
            FileNode(id="web/routes.py", path="web/routes.py", language="python", out_degree_structural=1),
            FileNode(id="pkg/service.py", path="pkg/service.py", language="python", in_degree_structural=1, out_degree_structural=1),
            FileNode(id="pkg/db.py", path="pkg/db.py", language="python", in_degree_structural=1, target_flag=True),
        ],
        structural_edges=[
            StructuralEdge(
                id="se:web/routes.py->pkg/service.py:calls",
                source="web/routes.py",
                target="pkg/service.py",
                relationship_type=RelationshipType.CALLS,
                evidence_count=1,
            ),
            StructuralEdge(
                id="se:pkg/service.py->pkg/db.py:calls",
                source="pkg/service.py",
                target="pkg/db.py",
                relationship_type=RelationshipType.CALLS,
                evidence_count=1,
            ),
        ],
        summary=GraphSummary(
            file_count=3,
            structural_edge_count=2,
            evidence_count=2,
            files_by_language={"python": 3},
            edges_by_relationship_type={"calls": 2},
        ),
        diagnostics=ProjectionDiagnostics(candidate_relation_count=2, emitted_edge_count=2),
    )


def build_grouping_artifact(repo_path: Path) -> ServiceGroupingArtifact:
    return ServiceGroupingArtifact(
        grouping_id="sg:repo:python_repo",
        template_version=ServiceTemplateVersion.V1,
        structural_graph_id="repo:python_repo",
        repo_path=str(repo_path),
        known_file_paths=["web/routes.py", "pkg/service.py", "pkg/db.py"],
        architecture_summary="Web entry reaches app and then data.",
        services=[
            ServiceDefinition(
                id="svc:web",
                name="Web",
                layer=ServiceLayer.EDGE,
                summary="HTTP entry",
                member_file_paths=["web/routes.py"],
            ),
            ServiceDefinition(
                id="svc:app",
                name="App",
                layer=ServiceLayer.APPLICATION,
                summary="Application logic",
                member_file_paths=["pkg/service.py"],
            ),
            ServiceDefinition(
                id="svc:data",
                name="Data",
                layer=ServiceLayer.DATA,
                summary="Persistence",
                member_file_paths=["pkg/db.py"],
            ),
        ],
        file_assignments=[
            ServiceFileAssignment(file_path="web/routes.py", assigned_service_id="svc:web", assignment_kind=ServiceAssignmentKind.PRIMARY, resolution_source=ServiceResolutionSource.LLM_PRIMARY),
            ServiceFileAssignment(file_path="pkg/service.py", assigned_service_id="svc:app", assignment_kind=ServiceAssignmentKind.PRIMARY, resolution_source=ServiceResolutionSource.LLM_PRIMARY),
            ServiceFileAssignment(file_path="pkg/db.py", assigned_service_id="svc:data", assignment_kind=ServiceAssignmentKind.PRIMARY, resolution_source=ServiceResolutionSource.LLM_PRIMARY),
        ],
        llm_invocation={
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "openrouter/test-model",
            "operation_name": "service_grouping.generate",
            "response_format_name": "LLMServiceGroupingPayload",
            "template_version": "service-grouping-v1",
            "prompt_version": "service-grouping-prompt-v3",
            "system_prompt": "system",
            "user_prompt": "user",
            "system_prompt_sha256": "sys",
            "user_prompt_sha256": "usr",
            "system_prompt_chars": 6,
            "user_prompt_chars": 4,
            "provider_request_id": "req_1",
            "finish_reason": "stop",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "duration_seconds": 0.1,
        },
        summary=ServiceGroupingSummary(
            service_count=3,
            inferred_service_count=3,
            file_count=3,
            shared_file_count=0,
            unclassified_file_count=0,
            ambiguous_file_count=0,
            invented_file_reference_count=0,
            dropped_service_count=0,
        ),
        diagnostics=ServiceGroupingDiagnostics(prompt_file_count=3, prompt_edge_count=2, total_prompt_chars=120),
    )


def build_service_graph_json(repo_path: Path) -> dict[str, object]:
    return {
        "service_graph_id": "svg:repo:python_repo",
        "grouping_id": "sg:repo:python_repo",
        "structural_graph_id": "repo:python_repo",
        "repo_path": str(repo_path),
        "nodes": [
            {
                "id": "svc:web",
                "name": "Web",
                "kind": "inferred",
                "layer": "edge",
                "summary": "HTTP entry",
                "member_file_paths": ["web/routes.py"],
                "file_count": 1,
                "files_by_language": {"python": 1},
            },
            {
                "id": "svc:app",
                "name": "App",
                "kind": "inferred",
                "layer": "application",
                "summary": "Application logic",
                "member_file_paths": ["pkg/service.py"],
                "file_count": 1,
                "files_by_language": {"python": 1},
            },
            {
                "id": "svc:data",
                "name": "Data",
                "kind": "inferred",
                "layer": "data",
                "summary": "Persistence",
                "member_file_paths": ["pkg/db.py"],
                "file_count": 1,
                "files_by_language": {"python": 1},
            },
        ],
        "service_edges": [
            {
                "id": "sve:svc:web->svc:app",
                "source": "svc:web",
                "target": "svc:app",
                "relationship_types": ["calls"],
                "supporting_structural_edge_ids": ["se:web/routes.py->pkg/service.py:calls"],
                "supporting_file_pairs": [{"source_file_path": "web/routes.py", "target_file_path": "pkg/service.py"}],
                "supporting_edge_count": 1,
            },
            {
                "id": "sve:svc:app->svc:data",
                "source": "svc:app",
                "target": "svc:data",
                "relationship_types": ["calls"],
                "supporting_structural_edge_ids": ["se:pkg/service.py->pkg/db.py:calls"],
                "supporting_file_pairs": [{"source_file_path": "pkg/service.py", "target_file_path": "pkg/db.py"}],
                "supporting_edge_count": 1,
            },
        ],
        "summary": {
            "service_count": 3,
            "service_edge_count": 2,
            "file_count": 3,
            "internal_structural_edge_count": 0,
            "inter_service_structural_edge_count": 2,
            "services_by_layer": {"application": 1, "data": 1, "edge": 1},
        },
        "diagnostics": {"unmapped_structural_edge_count": 0},
    }


def test_build_recommendation_input_from_structural_graph(tmp_path: Path) -> None:
    structural_graph = build_structural_artifact(tmp_path)
    structural_graph_path = tmp_path / "structural_graph.json"
    structural_graph_path.write_text(json.dumps(structural_graph.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    output_path = tmp_path / "recommendation_input.json"

    service = RecommendationInputBuilderService(get_logger("reporting-input-builder-test"))
    result = service.run(
        RecommendationInputBuildRequest(
            graph_scope=GraphScope.FILE,
            structural_graph_path=structural_graph_path,
            output_path=output_path,
            path_id="file-path",
            path_node_ids=["web/routes.py", "pkg/service.py", "pkg/db.py"],
            focal_file_paths=["pkg/db.py"],
        )
    )

    artifact = read_recommendation_report_input(output_path)
    assert result.output_path.exists()
    assert artifact.graph_scope == GraphScope.FILE
    assert [node.id for node in artifact.path_nodes] == ["web/routes.py", "pkg/service.py", "pkg/db.py"]
    assert artifact.path_edges[0].relationship_type == "calls"


def test_build_recommendation_input_from_service_graph(tmp_path: Path) -> None:
    structural_graph = build_structural_artifact(tmp_path)
    structural_graph_path = tmp_path / "structural_graph.json"
    structural_graph_path.write_text(json.dumps(structural_graph.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    grouping_path = tmp_path / "service_grouping.json"
    grouping_path.write_text(json.dumps(build_grouping_artifact(tmp_path).model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    service_graph_path = tmp_path / "service_graph.json"
    service_graph_path.write_text(json.dumps(build_service_graph_json(tmp_path), indent=2, sort_keys=True), encoding="utf-8")
    output_path = tmp_path / "service_recommendation_input.json"

    service = RecommendationInputBuilderService(get_logger("reporting-input-builder-test"))
    result = service.run(
        RecommendationInputBuildRequest(
            graph_scope=GraphScope.SERVICE,
            structural_graph_path=structural_graph_path,
            service_graph_path=service_graph_path,
            grouping_path=grouping_path,
            output_path=output_path,
            path_id="service-path",
            path_node_ids=["svc:web", "svc:app", "svc:data"],
        )
    )

    artifact = read_recommendation_report_input(output_path)
    assert result.output_path.exists()
    assert artifact.graph_scope == GraphScope.SERVICE
    assert artifact.graph_id == "svg:repo:python_repo"
    assert artifact.path_nodes[0].display_name == "Web"
    assert artifact.path_nodes[1].backing_file_paths == ["pkg/service.py"]
    assert artifact.path_edges[0].structural_basis_edge_ids == ["se:web/routes.py->pkg/service.py:calls"]


def test_cli_build_recommendation_input(monkeypatch, tmp_path: Path, capsys) -> None:
    class FakeSummary:
        def model_dump(self, mode="json"):
            return {
                "path_node_count": 2,
                "path_edge_count": 1,
                "focal_file_count": 0,
            }

    class FakeArtifact:
        summary = FakeSummary()

    class FakeService:
        def __init__(self, logger) -> None:
            self._logger = logger

        def run(self, request):
            assert request.graph_scope == GraphScope.FILE
            assert request.path_node_ids == ["web/routes.py", "pkg/service.py"]
            return type("Result", (), {"artifact": FakeArtifact(), "output_path": request.output_path})()

    monkeypatch.setattr("pathfinder.cli.RecommendationInputBuilderService", FakeService)

    exit_code = main([
        "build-recommendation-input",
        "--graph-scope",
        "file",
        "--structural-graph",
        str(tmp_path / "structural_graph.json"),
        "--path-node-id",
        "web/routes.py",
        "--path-node-id",
        "pkg/service.py",
        "--output",
        str(tmp_path / "out.json"),
    ])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["path_node_count"] == 2
