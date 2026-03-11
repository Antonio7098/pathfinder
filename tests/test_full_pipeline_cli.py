from __future__ import annotations

import json
import asyncio
from pathlib import Path

from pathfinder.cli import main
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredPrompt, TokenUsage
from pathfinder.observability.logging import get_logger
from pathfinder.pipeline.models import FullPipelineRequest, FullPipelineResult
from pathfinder.pipeline.service import FullPipelineService, _build_report_input_artifact, _select_best_path
from pathfinder.reporting.enums import RecommendationPriority, RecommendationTemplateVersion
from pathfinder.reporting.models import RecommendationItem, RecommendationPathOverview, RecommendationReportArtifact, RecommendationReportDiagnostics, RecommendationReportSummary
from pathfinder.services.enums import ServiceAssignmentKind, ServiceLayer, ServiceResolutionSource, ServiceTemplateVersion
from pathfinder.services.models import ServiceDefinition, ServiceFileAssignment, ServiceGraphArtifact, ServiceGraphDiagnostics, ServiceGraphEdge, ServiceGraphNode, ServiceGraphSummary, ServiceGroupingArtifact, ServiceGroupingDiagnostics, ServiceGroupingSummary
from pathfinder.structural.enums import GraphVersion, RelationshipType
from pathfinder.structural.models import FileNode, GraphSummary, ProjectionDiagnostics, StructuralEdge, StructuralEvidence, StructuralGraphArtifact


def build_invocation(operation_name: str, response_format_name: str) -> LLMInvocationRecord:
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
        model="openrouter/test-model",
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
        provider_request_id="req_1",
        finish_reason="stop",
        usage=TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        duration_seconds=0.1,
    )


def test_select_best_path_prefers_lowest_score() -> None:
    security_graph = {
        "graph_id": "repo:test",
        "nodes": [
            {
                "id": "web/routes.py",
                "path": "web/routes.py",
                "entrypoint_flag": True,
                "target_flag": False,
                "security_scores": {"exploitability": 0.9, "lateral_movement_value": 0.2},
                "normalized_risk_score": 0.7,
            },
            {
                "id": "pkg/service.py",
                "path": "pkg/service.py",
                "entrypoint_flag": False,
                "target_flag": False,
                "security_scores": {"lateral_movement_value": 0.8},
                "normalized_risk_score": 0.6,
            },
            {
                "id": "pkg/db.py",
                "path": "pkg/db.py",
                "entrypoint_flag": False,
                "target_flag": True,
                "security_scores": {"data_access_value": 1.0, "privilege_gain": 0.8},
                "normalized_risk_score": 0.9,
            },
        ],
        "attack_edges": [
            {
                "id": "ae:route-service",
                "source": "web/routes.py",
                "target": "pkg/service.py",
                "attack_type": "command_injection",
                "transition_likelihood": 0.9,
                "detection_risk": 0.1,
                "edge_attack_cost": 0.2,
                "confidence": 0.8,
                "rationale": "first hop",
            },
            {
                "id": "ae:service-db",
                "source": "pkg/service.py",
                "target": "pkg/db.py",
                "attack_type": "sql_injection",
                "transition_likelihood": 0.9,
                "detection_risk": 0.1,
                "edge_attack_cost": 0.1,
                "confidence": 0.8,
                "rationale": "best target hop",
            },
            {
                "id": "ae:route-db",
                "source": "web/routes.py",
                "target": "pkg/db.py",
                "attack_type": "sql_injection",
                "transition_likelihood": 0.1,
                "detection_risk": 0.9,
                "edge_attack_cost": 0.9,
                "confidence": 0.4,
                "rationale": "worse direct hop",
            },
        ],
    }

    selected = _select_best_path(security_graph)

    assert selected["nodes"] == ["web/routes.py", "pkg/service.py", "pkg/db.py"]
    assert selected["edges"] == ["ae:route-service", "ae:service-db"]
    assert len(selected["edge_details"]) == 2


def test_build_report_input_artifact_uses_repo_relative_paths(tmp_path: Path) -> None:
    selected = {
        "nodes": ["web/routes.py", "pkg/db.py"],
        "edges": ["ae:route-db"],
    }
    security_graph = {
        "graph_id": "repo:test",
        "nodes": [
            {
                "id": "web/routes.py",
                "path": "web/routes.py",
                "entrypoint_flag": True,
                "target_flag": False,
                "normalized_risk_score": 0.4,
                "confidence": 0.9,
                "rationale": "entry",
            },
            {
                "id": "pkg/db.py",
                "path": "pkg/db.py",
                "entrypoint_flag": False,
                "target_flag": True,
                "normalized_risk_score": 0.9,
                "confidence": 0.8,
                "rationale": "target",
            },
        ],
        "attack_edges": [
            {
                "id": "ae:route-db",
                "source": "web/routes.py",
                "target": "pkg/db.py",
                "attack_type": "sql_injection",
                "edge_attack_cost": 0.4,
                "confidence": 0.7,
                "rationale": "edge",
                "structural_basis_edge_ids": ["se:web/routes.py->pkg/db.py:calls"],
            }
        ],
    }

    artifact = _build_report_input_artifact(repo_path=tmp_path, security_graph=security_graph, selected_path=selected)

    assert artifact.repo_path == str(tmp_path)
    assert [node.path for node in artifact.path_nodes] == ["web/routes.py", "pkg/db.py"]
    assert artifact.focal_files[0].path == "web/routes.py"


def test_cli_run_full_pipeline(monkeypatch, tmp_path: Path, capsys) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    class FakeService:
        def __init__(self, logger) -> None:
            self._logger = logger

        async def run(self, request):
            assert request.repo_path == repo_path
            assert request.output_dir == tmp_path / "out"
            return FullPipelineResult(
                structural_graph_path=tmp_path / "out" / "structural_graph.json",
                raw_codegraph_path=tmp_path / "out" / "raw_codegraph.json",
                service_grouping_path=tmp_path / "out" / "service_grouping.json",
                service_graph_path=tmp_path / "out" / "service_graph.json",
                security_graph_path=tmp_path / "out" / "security_graph.json",
                selected_path_input_path=tmp_path / "out" / "recommendation_input.json",
                recommendation_report_path=tmp_path / "out" / "recommendation_report.json",
                dashboard_path=tmp_path / "out" / "dashboard.html",
            )

    monkeypatch.setattr("pathfinder.cli.FullPipelineService", FakeService)

    exit_code = main(
        [
            "run-full-pipeline",
            "--repo",
            str(repo_path),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["dashboard_path"].endswith("dashboard.html")


def test_full_pipeline_service_stageflow_smoke(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "web").mkdir(parents=True)
    (repo_path / "pkg").mkdir(parents=True)
    (repo_path / "web" / "routes.py").write_text("from pkg.service import get_user\n", encoding="utf-8")
    (repo_path / "pkg" / "service.py").write_text("from pkg.db import query_user\n", encoding="utf-8")
    (repo_path / "pkg" / "db.py").write_text("def query_user():\n    return 1\n", encoding="utf-8")

    structural_artifact = StructuralGraphArtifact(
        graph_id="repo:repo",
        version=GraphVersion.MVP_V1,
        repo_path=str(repo_path),
        nodes=[
            FileNode(id="pkg/db.py", path="pkg/db.py", language="python", target_flag=True),
            FileNode(id="pkg/service.py", path="pkg/service.py", language="python"),
            FileNode(id="web/routes.py", path="web/routes.py", language="python", entrypoint_flag=True),
        ],
        structural_edges=[
            StructuralEdge(
                id="se:web/routes.py->pkg/service.py:calls",
                source="web/routes.py",
                target="pkg/service.py",
                relationship_type=RelationshipType.CALLS,
                evidence_count=1,
                evidence_relations=["uses_symbol"],
                provenance=[StructuralEvidence(raw_relation="uses_symbol", source_block_id="1", target_block_id="2")],
            ),
            StructuralEdge(
                id="se:pkg/service.py->pkg/db.py:calls",
                source="pkg/service.py",
                target="pkg/db.py",
                relationship_type=RelationshipType.CALLS,
                evidence_count=1,
                evidence_relations=["uses_symbol"],
                provenance=[StructuralEvidence(raw_relation="uses_symbol", source_block_id="3", target_block_id="4")],
            ),
        ],
        summary=GraphSummary(
            file_count=3,
            structural_edge_count=2,
            attack_edge_count=0,
            evidence_count=2,
            files_by_language={"python": 3},
            edges_by_relationship_type={"calls": 2},
        ),
        diagnostics=ProjectionDiagnostics(candidate_relation_count=2, emitted_edge_count=2),
    )

    class FakeStructuralService:
        def __init__(self, logger) -> None:
            self._logger = logger

        def run(self, request):
            request.output_path.write_text(json.dumps(structural_artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
            request.raw_codegraph_output_path.write_text("{}", encoding="utf-8")
            return type(
                "Result",
                (),
                {
                    "artifact": structural_artifact,
                    "output_path": request.output_path,
                    "raw_codegraph_output_path": request.raw_codegraph_output_path,
                    "duration_seconds": 0.1,
                },
            )()

    class FakeGroupingService:
        def run(self, request):
            artifact = ServiceGroupingArtifact(
                grouping_id="sg:repo:test",
                template_version=ServiceTemplateVersion.V1,
                structural_graph_id="repo:repo",
                repo_path=str(repo_path),
                known_file_paths=["web/routes.py", "pkg/service.py", "pkg/db.py"],
                architecture_summary="Simple app.",
                services=[
                    ServiceDefinition(id="svc:web", name="Web", layer=ServiceLayer.EDGE, summary="Edge", member_file_paths=["web/routes.py"]),
                    ServiceDefinition(id="svc:app", name="App", layer=ServiceLayer.APPLICATION, summary="App", member_file_paths=["pkg/service.py", "pkg/db.py"]),
                ],
                file_assignments=[
                    ServiceFileAssignment(file_path="web/routes.py", assigned_service_id="svc:web", assignment_kind=ServiceAssignmentKind.PRIMARY, resolution_source=ServiceResolutionSource.LLM_PRIMARY),
                    ServiceFileAssignment(file_path="pkg/service.py", assigned_service_id="svc:app", assignment_kind=ServiceAssignmentKind.PRIMARY, resolution_source=ServiceResolutionSource.LLM_PRIMARY),
                    ServiceFileAssignment(file_path="pkg/db.py", assigned_service_id="svc:app", assignment_kind=ServiceAssignmentKind.PRIMARY, resolution_source=ServiceResolutionSource.LLM_PRIMARY),
                ],
                llm_invocation=build_invocation("service_grouping.generate", "LLMServiceGroupingPayload"),
                summary=ServiceGroupingSummary(service_count=2, inferred_service_count=2, file_count=3, shared_file_count=0, unclassified_file_count=0, ambiguous_file_count=0, invented_file_reference_count=0, dropped_service_count=0),
                diagnostics=ServiceGroupingDiagnostics(prompt_file_count=3, prompt_edge_count=2, total_prompt_chars=10),
            )
            request.output_path.write_text(json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
            return type("Result", (), {"artifact": artifact, "output_path": request.output_path, "duration_seconds": 0.1})()

    class FakeServiceGraphService:
        def __init__(self, logger) -> None:
            self._logger = logger

        def run(self, request):
            artifact = ServiceGraphArtifact(
                service_graph_id="svg:repo:test",
                grouping_id="sg:repo:test",
                structural_graph_id="repo:repo",
                repo_path=str(repo_path),
                nodes=[
                    ServiceGraphNode(id="svc:web", name="Web", kind="inferred", layer=ServiceLayer.EDGE, summary="Edge", member_file_paths=["web/routes.py"], file_count=1, files_by_language={"python": 1}),
                    ServiceGraphNode(id="svc:app", name="App", kind="inferred", layer=ServiceLayer.APPLICATION, summary="App", member_file_paths=["pkg/service.py", "pkg/db.py"], file_count=2, files_by_language={"python": 2}),
                ],
                service_edges=[
                    ServiceGraphEdge(id="sve:web-app", source="svc:web", target="svc:app", relationship_types=["calls"], supporting_structural_edge_ids=["se:web/routes.py->pkg/service.py:calls"], supporting_edge_count=1)
                ],
                summary=ServiceGraphSummary(service_count=2, service_edge_count=1, file_count=3, internal_structural_edge_count=1, inter_service_structural_edge_count=1, services_by_layer={"edge": 1, "application": 1}),
                diagnostics=ServiceGraphDiagnostics(unmapped_structural_edge_count=0),
            )
            request.output_path.write_text(json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
            return type("Result", (), {"artifact": artifact, "output_path": request.output_path, "duration_seconds": 0.1})()

    class FakeAI:
        def __init__(self, model="gpt-4o", *, logger=None) -> None:
            self.model = model

        def analyze_node(self, file_path):
            relative = Path(file_path).relative_to(repo_path).as_posix()
            base = {
                "tags": [],
                "confidence": 0.9,
                "rationale": "grounded",
                "security_scores": {
                    "exploitability": 0.7,
                    "privilege_gain": 0.6,
                    "data_access_value": 0.6,
                    "lateral_movement_value": 0.5,
                    "detection_risk": 0.2,
                    "confidence": 0.9,
                    "normalized_risk_score": 0.7,
                },
                "id": relative,
                "path": relative,
                "node_type": "file",
                "normalized_risk_score": 0.7,
            }
            return base

        def analyze_edge(self, structural_edge, source_node, target_node):
            return [
                {
                    "id": f"ae:{structural_edge['id']}",
                    "edge_type": "attack_transition",
                    "source": structural_edge["source"],
                    "target": structural_edge["target"],
                    "attack_type": "sql_injection" if target_node["id"].endswith("db.py") else "command_injection",
                    "transition_likelihood": 0.9,
                    "required_capability": "low",
                    "detection_risk": 0.1,
                    "edge_attack_cost": 0.2,
                    "confidence": 0.8,
                    "rationale": "grounded",
                    "structural_basis_edge_ids": [structural_edge["id"]],
                    "excluded_flag": False,
                }
            ]

    class FakeRecommendationService:
        def run(self, request):
            artifact = RecommendationReportArtifact(
                report_id="rr:path:test",
                template_version=RecommendationTemplateVersion.V1,
                input_artifact_id="input:test",
                repo_path=str(repo_path),
                known_file_paths=["web/routes.py", "pkg/service.py", "pkg/db.py"],
                path_overview=RecommendationPathOverview(
                    path_id="path:web->db",
                    ordered_node_ids=["web/routes.py", "pkg/service.py", "pkg/db.py"],
                    ordered_edge_ids=["ae:se:web/routes.py->pkg/service.py:calls", "ae:se:pkg/service.py->pkg/db.py:calls"],
                    ordered_file_paths=["web/routes.py", "pkg/service.py", "pkg/db.py"],
                    path_narrative="Route to service to db.",
                    target_rationale="Database access matters.",
                    top_priority_file_path="web/routes.py",
                    top_priority_rationale="First choke point.",
                ),
                recommendations=[
                    RecommendationItem(
                        id="recommendation:1",
                        priority=RecommendationPriority.HIGH,
                        title="Validate route input",
                        summary="Add validation before database calls.",
                        mitigation_steps=["Validate request parameters", "Use parameterized queries"],
                        primary_file_path="web/routes.py",
                        supporting_file_paths=["pkg/service.py"],
                        supporting_node_ids=["web/routes.py"],
                        supporting_edge_ids=["ae:se:web/routes.py->pkg/service.py:calls"],
                        confidence=0.9,
                    )
                ],
                llm_invocation=build_invocation("recommendation_report.generate", "LLMRecommendationReportPayload"),
                summary=RecommendationReportSummary(path_node_count=3, path_edge_count=2, known_file_count=3, loaded_file_count=3, missing_file_count=0, truncated_file_count=0, dropped_file_count=0, recommendation_count=1, citation_count=4),
                diagnostics=RecommendationReportDiagnostics(total_prompt_chars=20),
            )
            request.output_path.write_text(json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
            return type("Result", (), {"artifact": artifact, "output_path": request.output_path, "duration_seconds": 0.1})()

    monkeypatch.setattr("pathfinder.pipeline.service.StructuralExtractionService", FakeStructuralService)
    monkeypatch.setattr("pathfinder.pipeline.service.create_openrouter_service_grouping_service", lambda logger, model_override=None, timeout_seconds=60.0: FakeGroupingService())
    monkeypatch.setattr("pathfinder.pipeline.service.ServiceGraphService", FakeServiceGraphService)
    monkeypatch.setattr("pathfinder.pipeline.service.PathfinderAI", FakeAI)
    monkeypatch.setattr("pathfinder.pipeline.service.create_openrouter_recommendation_report_service", lambda logger, model_override=None, timeout_seconds=60.0: FakeRecommendationService())

    service = FullPipelineService(get_logger("test"))
    result = asyncio.run(
        service.run(
            request=FullPipelineRequest(
                repo_path=repo_path,
                output_dir=tmp_path / "out",
                timeout_seconds=30.0,
            )
        )
    )

    assert result.dashboard_path.exists()
    assert "Pathfinder Attack Path Dashboard" in result.dashboard_path.read_text(encoding="utf-8")
