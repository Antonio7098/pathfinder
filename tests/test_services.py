from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pathfinder.adapters.codegraph import read_raw_codegraph_document
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredLLMResult, StructuredPrompt, TokenUsage
from pathfinder.observability.logging import get_logger
from pathfinder.services.enums import ServiceAssignmentKind, ServiceLayer, ServiceResolutionSource, ServiceTemplateVersion
from pathfinder.services.graphcode_context import ServiceGroupingGraphcodeContextBuilder
from pathfinder.services.graph_builder import ServiceGraphBuilder
from pathfinder.services.io import read_service_graph, read_service_grouping
from pathfinder.services.models import LLMProposedService, LLMServiceGroupingPayload
from pathfinder.services.resolver import ServiceGroupingResolver
from pathfinder.services.service import ServiceGraphRequest, ServiceGraphService, ServiceGroupingRequest, ServiceGroupingService
from pathfinder.structural.io import read_structural_graph
from pathfinder.structural.service import StructuralExtractionRequest, StructuralExtractionService


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def build_structural_artifact(repo_name: str, tmp_path: Path):
    service = StructuralExtractionService(get_logger("services-test"))
    output_path = tmp_path / f"{repo_name}_structural_graph.json"
    result = service.run(
        StructuralExtractionRequest(
            repo_path=FIXTURES / repo_name,
            output_path=output_path,
            raw_codegraph_output_path=tmp_path / f"{repo_name}_raw_codegraph.json",
        )
    )
    return result, read_structural_graph(output_path)


def build_invocation() -> LLMInvocationRecord:
    prompt = StructuredPrompt(
        template_version="service-grouping-v1",
        prompt_version="service-grouping-prompt-v3",
        system_prompt="system",
        user_prompt="user",
        system_prompt_sha256="sys",
        user_prompt_sha256="usr",
    )
    return LLMInvocationRecord(
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
        usage=TokenUsage(input_tokens=10, output_tokens=15, total_tokens=25),
        duration_seconds=0.3,
    )


def build_grouping_payload() -> LLMServiceGroupingPayload:
    return LLMServiceGroupingPayload(
        architecture_summary="A web entry layer calls application logic which then reaches the data layer.",
        services=[
            LLMProposedService(
                name="Web Interface",
                layer=ServiceLayer.EDGE,
                summary="HTTP route handling and entrypoints.",
                file_paths=["web/routes.py"],
                confidence=0.9,
                rationale="The file exposes request handling.",
            ),
            LLMProposedService(
                name="Application Service",
                layer=ServiceLayer.APPLICATION,
                summary="Business logic and orchestration.",
                file_paths=["pkg/service.py"],
                confidence=0.85,
                rationale="The file coordinates user retrieval.",
            ),
            LLMProposedService(
                name="Data Access",
                layer=ServiceLayer.DATA,
                summary="Database access and persistence.",
                file_paths=["pkg/db.py"],
                confidence=0.88,
                rationale="The file issues database queries.",
            ),
        ],
    )


@dataclass
class FakeLLMClient:
    payload: LLMServiceGroupingPayload
    expected_symbol_name: str | None = None

    def generate(self, request, *, response_model):
        assert response_model is LLMServiceGroupingPayload
        assert request.prompt.template_version == ServiceTemplateVersion.V1.value
        if self.expected_symbol_name is not None:
            prompt_payload = json.loads(request.prompt.user_prompt)
            file_profiles = prompt_payload["graphcode_context"]["file_profiles"]
            exported_names = [symbol["name"] for profile in file_profiles for symbol in profile["exported_symbols"]]
            assert self.expected_symbol_name in exported_names
        return StructuredLLMResult(parsed_output=self.payload, invocation=build_invocation())


def test_service_grouping_graphcode_context_builder_extracts_symbol_profiles(tmp_path: Path) -> None:
    result, structural_graph = build_structural_artifact("python_repo", tmp_path)
    assert result.raw_codegraph_output_path is not None

    evidence = ServiceGroupingGraphcodeContextBuilder().build(
        structural_graph=structural_graph,
        raw_codegraph=read_raw_codegraph_document(result.raw_codegraph_output_path),
    )

    assert evidence.available is True
    assert evidence.symbol_block_count >= 3
    profile_by_path = {profile.path: profile for profile in evidence.file_profiles}
    assert profile_by_path["web/routes.py"].exported_symbols[0].name == "handler"
    assert "api_surface" in profile_by_path["web/routes.py"].role_hints
    assert profile_by_path["pkg/service.py"].outgoing_symbol_relation_count >= 1
    directory_by_name = {summary.directory: summary for summary in evidence.directory_summaries}
    assert directory_by_name["web"].role_hint_counts["api_surface"] >= 1
    assert directory_by_name["web"].representative_files[0].path == "web/routes.py"
    pair_paths = {(item.source_path, item.target_path) for item in evidence.file_pair_summaries}
    assert ("web/routes.py", "pkg/service.py") in pair_paths


def test_service_grouping_resolver_creates_shared_and_dropped_buckets(tmp_path: Path) -> None:
    _, structural_graph = build_structural_artifact("python_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="Routes and storage overlap around one shared file.",
        services=[
            LLMProposedService(
                name="Routes",
                layer=ServiceLayer.EDGE,
                summary="Inbound handling.",
                file_paths=["web/routes.py", "pkg/service.py"],
                confidence=0.9,
            ),
            LLMProposedService(
                name="Storage",
                layer=ServiceLayer.DATA,
                summary="Persistence.",
                file_paths=["pkg/service.py", "pkg/db.py", "pkg/missing.py"],
                confidence=0.8,
            ),
            LLMProposedService(
                name="Empty",
                layer=ServiceLayer.UNKNOWN,
                summary="Should drop.",
                file_paths=["ghost.py"],
                confidence=0.4,
            ),
        ],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    assignments = {item.file_path: item for item in artifact.file_assignments}
    assert assignments["pkg/service.py"].assignment_kind == ServiceAssignmentKind.SHARED
    assert artifact.summary.ambiguous_file_count == 1
    assert artifact.summary.invented_file_reference_count == 2
    assert artifact.summary.dropped_service_count == 1
    assert artifact.diagnostics.shared_file_paths == ["pkg/service.py"]
    assert "Empty" in artifact.diagnostics.dropped_service_names


def test_service_grouping_resolver_promotes_unclassified_by_connectivity(tmp_path: Path) -> None:
    _, structural_graph = build_structural_artifact("python_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="One inferred service with adjacent omitted files.",
        services=[
            LLMProposedService(
                name="Application Service",
                layer=ServiceLayer.APPLICATION,
                summary="Business logic.",
                file_paths=["pkg/service.py"],
                confidence=0.9,
            )
        ],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    assignments = {item.file_path: item for item in artifact.file_assignments}
    assert assignments["pkg/db.py"].assignment_kind == ServiceAssignmentKind.PRIMARY
    assert assignments["pkg/db.py"].resolution_source == ServiceResolutionSource.CONNECTIVITY_PRIMARY
    assert assignments["web/routes.py"].assignment_kind == ServiceAssignmentKind.PRIMARY
    assert assignments["web/routes.py"].resolution_source == ServiceResolutionSource.CONNECTIVITY_PRIMARY
    assert artifact.summary.unclassified_file_count == 0
    assert artifact.diagnostics.connectivity_promoted_file_paths == ["pkg/db.py", "web/routes.py"]


def test_service_grouping_resolver_clusters_remaining_unclassified_files(tmp_path: Path) -> None:
    _, structural_graph = build_structural_artifact("python_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="No direct service proposals.",
        services=[],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    service_names = {service.name for service in artifact.services}
    assignments = {item.file_path: item for item in artifact.file_assignments}
    assert service_names == {"Pkg Cluster", "Unclassified"}
    assert assignments["pkg/service.py"].resolution_source == ServiceResolutionSource.CLUSTER_PRIMARY
    assert assignments["pkg/db.py"].resolution_source == ServiceResolutionSource.CLUSTER_PRIMARY
    assert assignments["web/routes.py"].resolution_source == ServiceResolutionSource.FALLBACK_UNCLASSIFIED
    assert artifact.summary.unclassified_file_count == 1
    assert artifact.diagnostics.cluster_promoted_file_paths == ["pkg/db.py", "pkg/service.py"]


def test_service_graph_builder_aggregates_inter_service_edges(tmp_path: Path) -> None:
    _, structural_graph = build_structural_artifact("python_repo", tmp_path)
    grouping_artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=build_grouping_payload(),
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    artifact = ServiceGraphBuilder().build(structural_graph=structural_graph, grouping_artifact=grouping_artifact)

    edge_ids = [edge.id for edge in artifact.service_edges]
    assert edge_ids == [
        "sve:svc:application-service->svc:data-access",
        "sve:svc:web-interface->svc:application-service",
    ]
    assert artifact.summary.inter_service_structural_edge_count == 4
    assert artifact.summary.internal_structural_edge_count == 0
    assert artifact.summary.services_by_layer == {"application": 1, "data": 1, "edge": 1}


def test_service_grouping_service_writes_grounded_artifact(tmp_path: Path) -> None:
    result, structural_graph = build_structural_artifact("python_repo", tmp_path)
    input_path = tmp_path / "structural_graph.json"
    input_path.write_text(json.dumps(structural_graph.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    output_path = tmp_path / "service_grouping.json"

    service = ServiceGroupingService(
        get_logger("services-test"),
        llm_client=FakeLLMClient(build_grouping_payload(), expected_symbol_name="handler"),
        model="openrouter/test-model",
    )

    result = service.run(
        ServiceGroupingRequest(
            input_path=input_path,
            output_path=output_path,
            raw_codegraph_input_path=result.raw_codegraph_output_path,
        )
    )
    artifact = read_service_grouping(output_path)
    assert result.output_path.exists()
    assert artifact.grouping_id == "sg:repo:python_repo"
    assert artifact.summary.service_count == 3
    assert artifact.summary.file_count == 3
    assert artifact.llm_invocation.model == "openrouter/test-model"


def test_service_graph_service_writes_service_graph(tmp_path: Path) -> None:
    _, structural_graph = build_structural_artifact("python_repo", tmp_path)
    structural_graph_path = tmp_path / "structural_graph.json"
    structural_graph_path.write_text(json.dumps(structural_graph.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    grouping_artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=build_grouping_payload(),
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )
    grouping_path = tmp_path / "service_grouping.json"
    grouping_path.write_text(json.dumps(grouping_artifact.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    output_path = tmp_path / "service_graph.json"

    service = ServiceGraphService(get_logger("services-test"))
    result = service.run(
        ServiceGraphRequest(
            structural_graph_path=structural_graph_path,
            grouping_path=grouping_path,
            output_path=output_path,
        )
    )

    artifact = read_service_graph(output_path)
    assert result.output_path.exists()
    assert artifact.service_graph_id == "svg:repo:python_repo"
    assert artifact.summary.service_edge_count == 2
    assert artifact.summary.service_count == 3