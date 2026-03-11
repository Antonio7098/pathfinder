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


def build_structural_artifact_from_repo(repo_path: Path, repo_name: str, tmp_path: Path):
    service = StructuralExtractionService(get_logger("services-test"))
    output_path = tmp_path / f"{repo_name}_structural_graph.json"
    result = service.run(
        StructuralExtractionRequest(
            repo_path=repo_path,
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
    assert service_names == {"Pkg Cluster", "Web Cluster"}
    assert assignments["pkg/service.py"].resolution_source == ServiceResolutionSource.CLUSTER_PRIMARY
    assert assignments["pkg/db.py"].resolution_source == ServiceResolutionSource.CLUSTER_PRIMARY
    assert assignments["web/routes.py"].resolution_source == ServiceResolutionSource.CLUSTER_PRIMARY
    assert artifact.summary.unclassified_file_count == 0
    assert artifact.diagnostics.cluster_promoted_file_paths == ["pkg/db.py", "pkg/service.py", "web/routes.py"]


def test_service_grouping_resolver_recovers_empty_named_services_from_directory_buckets(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "app" / "dashboard").mkdir(parents=True)
    (repo_path / "app" / "reporting").mkdir(parents=True)
    (repo_path / "app" / "shared").mkdir(parents=True)
    (repo_path / "app" / "dashboard" / "view.py").write_text("from app.shared.logging import log\n", encoding="utf-8")
    (repo_path / "app" / "dashboard" / "controller.py").write_text("from app.reporting.report import build\n", encoding="utf-8")
    (repo_path / "app" / "reporting" / "report.py").write_text("def build():\n    return {}\n", encoding="utf-8")
    (repo_path / "app" / "reporting" / "writer.py").write_text("from app.shared.logging import log\n", encoding="utf-8")
    (repo_path / "app" / "shared" / "logging.py").write_text("def log():\n    return None\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "recovery_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="Dashboard and reporting services with shared logging.",
        services=[
            LLMProposedService(name="Dashboard", layer=ServiceLayer.EDGE, summary="UI layer.", file_paths=["dashboard.py"]),
            LLMProposedService(name="Reporting", layer=ServiceLayer.APPLICATION, summary="Reporting layer.", file_paths=["reporting.py"]),
        ],
        shared_file_paths=["app/shared/logging.py"],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    services_by_name = {service.name: service for service in artifact.services}
    assert services_by_name["Dashboard"].member_file_paths == [
        "app/dashboard/controller.py",
        "app/dashboard/view.py",
    ]
    assert services_by_name["Reporting"].member_file_paths == [
        "app/reporting/report.py",
        "app/reporting/writer.py",
    ]
    assert artifact.summary.dropped_service_count == 0


def test_service_grouping_resolver_recovers_camel_case_service_names_from_directory_buckets(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "pkg" / "reporting").mkdir(parents=True)
    (repo_path / "pkg" / "structural").mkdir(parents=True)
    (repo_path / "pkg" / "reporting" / "writer.py").write_text("def write():\n    return None\n", encoding="utf-8")
    (repo_path / "pkg" / "reporting" / "models.py").write_text("class Item:\n    pass\n", encoding="utf-8")
    (repo_path / "pkg" / "structural" / "graph.py").write_text("def build():\n    return {}\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "camel_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="Reporting and structural services.",
        services=[
            LLMProposedService(name="ReportingService", layer=ServiceLayer.APPLICATION, summary="Reporting.", file_paths=[]),
            LLMProposedService(name="StructuralGraphService", layer=ServiceLayer.APPLICATION, summary="Structural.", file_paths=[]),
        ],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    services_by_name = {service.name: service for service in artifact.services}
    assert services_by_name["ReportingService"].member_file_paths == [
        "pkg/reporting/models.py",
        "pkg/reporting/writer.py",
    ]
    assert services_by_name["StructuralGraphService"].member_file_paths == [
        "pkg/structural/graph.py",
    ]


def test_service_grouping_resolver_expands_single_grounded_path_to_directory_bucket(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "pkg" / "observability").mkdir(parents=True)
    (repo_path / "pkg" / "observability" / "__init__.py").write_text("", encoding="utf-8")
    (repo_path / "pkg" / "observability" / "logging.py").write_text("def log():\n    return None\n", encoding="utf-8")
    (repo_path / "pkg" / "app.py").write_text("from pkg.observability.logging import log\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "bucket_expand_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="Observability helper plus app entry.",
        services=[
            LLMProposedService(
                name="observability",
                layer=ServiceLayer.SHARED,
                summary="Logging helpers.",
                file_paths=["pkg/observability/logging.py"],
            )
        ],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    services_by_name = {service.name: service for service in artifact.services}
    assert services_by_name["observability"].member_file_paths == [
        "pkg/observability/__init__.py",
        "pkg/observability/logging.py",
    ]


def test_service_grouping_resolver_clusters_remaining_files_by_second_level_prefix(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "app" / "dashboard").mkdir(parents=True)
    (repo_path / "app" / "reporting").mkdir(parents=True)
    (repo_path / "app" / "llm").mkdir(parents=True)
    (repo_path / "app" / "dashboard" / "view.py").write_text("def render():\n    return None\n", encoding="utf-8")
    (repo_path / "app" / "dashboard" / "controller.py").write_text("from app.reporting.report import build\n", encoding="utf-8")
    (repo_path / "app" / "reporting" / "report.py").write_text("def build():\n    return {}\n", encoding="utf-8")
    (repo_path / "app" / "reporting" / "writer.py").write_text("from app.llm.client import ask\n", encoding="utf-8")
    (repo_path / "app" / "llm" / "client.py").write_text("def ask():\n    return 'ok'\n", encoding="utf-8")
    (repo_path / "app" / "llm" / "prompt.py").write_text("SYSTEM = 'x'\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "cluster_repo", tmp_path)
    payload = LLMServiceGroupingPayload(architecture_summary="No direct service proposals.", services=[])

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    service_names = {service.name for service in artifact.services}
    assert service_names == {
        "App Dashboard Cluster",
        "App Llm Cluster",
        "App Reporting Cluster",
    }
    assert artifact.summary.unclassified_file_count == 0
    assert artifact.diagnostics.cluster_promoted_file_paths == [
        "app/dashboard/controller.py",
        "app/dashboard/view.py",
        "app/llm/client.py",
        "app/llm/prompt.py",
        "app/reporting/report.py",
        "app/reporting/writer.py",
    ]


def test_service_grouping_resolver_handles_badly_organized_repo_with_root_and_misc_clusters(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "misc").mkdir(parents=True)
    (repo_path / "api.py").write_text("from auth import login\n", encoding="utf-8")
    (repo_path / "auth.py").write_text("from db import fetch_user\n", encoding="utf-8")
    (repo_path / "db.py").write_text("def fetch_user():\n    return {}\n", encoding="utf-8")
    (repo_path / "reporting.py").write_text("from util import emit\n", encoding="utf-8")
    (repo_path / "util.py").write_text("def emit():\n    return None\n", encoding="utf-8")
    (repo_path / "misc" / "cleanup.py").write_text("def run():\n    return None\n", encoding="utf-8")
    (repo_path / "misc" / "legacy.py").write_text("from util import emit\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "python_messy_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="A messy flat repo with some legacy utilities.",
        services=[],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    services_by_name = {service.name: service for service in artifact.services}
    assert services_by_name["Root Cluster"].member_file_paths == [
        "api.py",
        "auth.py",
        "db.py",
        "reporting.py",
        "util.py",
    ]
    assert services_by_name["Misc Cluster"].member_file_paths == [
        "misc/cleanup.py",
        "misc/legacy.py",
    ]
    assert artifact.summary.unclassified_file_count == 0
    assert artifact.summary.dropped_service_count == 0


def test_service_grouping_resolver_handles_mixed_language_messy_repo(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "src" / "reporting").mkdir(parents=True)
    (repo_path / "src" / "shared").mkdir(parents=True)
    (repo_path / "web").mkdir(parents=True)
    (repo_path / "main.py").write_text("from scripts.bootstrap import run\n", encoding="utf-8")
    (repo_path / "scripts" / "bootstrap.py").write_text("from src.reporting.writer import write_report\n", encoding="utf-8")
    (repo_path / "src" / "reporting" / "writer.py").write_text("from src.shared.util import slugify\n", encoding="utf-8")
    (repo_path / "src" / "shared" / "util.py").write_text("def slugify(value: str) -> str:\n    return value\n", encoding="utf-8")
    (repo_path / "web" / "app.ts").write_text("import { client } from './client';\nexport const app = client;\n", encoding="utf-8")
    (repo_path / "web" / "client.ts").write_text("export const client = {};\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "mixed_messy_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="Mixed flat scripts, src package, and web code.",
        services=[],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    services_by_name = {service.name: service for service in artifact.services}
    assert services_by_name["Root Cluster"].member_file_paths == ["main.py"]
    assert services_by_name["Scripts Cluster"].member_file_paths == ["scripts/bootstrap.py"]
    assert services_by_name["Src Reporting Cluster"].member_file_paths == ["src/reporting/writer.py"]
    assert services_by_name["Src Shared Cluster"].member_file_paths == ["src/shared/util.py"]
    assert services_by_name["Web Cluster"].member_file_paths == ["web/app.ts", "web/client.ts"]


def test_service_grouping_resolver_prefers_structure_over_misleading_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "core").mkdir(parents=True)
    (repo_path / "engine").mkdir(parents=True)
    (repo_path / "helpers").mkdir(parents=True)
    (repo_path / "core" / "api.py").write_text("from core.db import query\n", encoding="utf-8")
    (repo_path / "core" / "db.py").write_text("def query():\n    return {}\n", encoding="utf-8")
    (repo_path / "engine" / "service.py").write_text("from helpers.api_utils import wrap\n", encoding="utf-8")
    (repo_path / "helpers" / "api_utils.py").write_text("from helpers.db_utils import connect\n", encoding="utf-8")
    (repo_path / "helpers" / "db_utils.py").write_text("def connect():\n    return None\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "misleading_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="Names conflict with structure.",
        services=[],
    )

    artifact = ServiceGroupingResolver().resolve(
        structural_graph=structural_graph,
        payload=payload,
        template_version=ServiceTemplateVersion.V1,
        llm_invocation=build_invocation(),
    )

    services_by_name = {service.name: service for service in artifact.services}
    assert services_by_name["Core Cluster"].member_file_paths == ["core/api.py", "core/db.py"]
    assert services_by_name["Engine Cluster"].member_file_paths == ["engine/service.py"]
    assert services_by_name["Helpers Cluster"].member_file_paths == ["helpers/api_utils.py", "helpers/db_utils.py"]


def test_service_grouping_resolver_does_not_connectivity_promote_across_unrelated_directory_buckets(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "app" / "llm").mkdir(parents=True)
    (repo_path / "app" / "services").mkdir(parents=True)
    (repo_path / "app" / "llm" / "client.py").write_text("from app.services.logic import run\n", encoding="utf-8")
    (repo_path / "app" / "llm" / "prompts.py").write_text("TEMPLATE = 'x'\n", encoding="utf-8")
    (repo_path / "app" / "services" / "logic.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    (repo_path / "app" / "services" / "resolver.py").write_text("from app.llm.client import run\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "bucket_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="LLM helpers plus services logic.",
        services=[
            LLMProposedService(
                name="llm",
                layer=ServiceLayer.DOMAIN,
                summary="Prompting and model IO.",
                file_paths=["app/llm/client.py", "app/llm/prompts.py"],
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
    assert assignments["app/services/logic.py"].resolution_source == ServiceResolutionSource.CLUSTER_PRIMARY
    assert assignments["app/services/resolver.py"].resolution_source == ServiceResolutionSource.CLUSTER_PRIMARY
    assert assignments["app/services/logic.py"].assigned_service_id != assignments["app/llm/client.py"].assigned_service_id


def test_service_grouping_resolver_requires_multiple_broad_directory_votes(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "pkg" / "reporting").mkdir(parents=True)
    (repo_path / "pkg" / "llm").mkdir(parents=True)
    (repo_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo_path / "pkg" / "reporting" / "writer.py").write_text("def write():\n    return None\n", encoding="utf-8")
    (repo_path / "pkg" / "llm" / "client.py").write_text("def ask():\n    return None\n", encoding="utf-8")

    _, structural_graph = build_structural_artifact_from_repo(repo_path, "broad_parent_repo", tmp_path)
    payload = LLMServiceGroupingPayload(
        architecture_summary="Reporting with a package root file.",
        services=[
            LLMProposedService(
                name="reporting",
                layer=ServiceLayer.APPLICATION,
                summary="Report generation.",
                file_paths=["pkg/reporting/writer.py"],
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
    assert assignments["pkg/llm/client.py"].assigned_service_id != assignments["pkg/reporting/writer.py"].assigned_service_id


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
