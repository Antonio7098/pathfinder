"""Recommendation report orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict

from pathfinder.llm import LLMProvider, OpenAIStructuredLLMClient, OpenRouterSettings, StructuredLLMRequest
from pathfinder.observability.logging import log_event
from pathfinder.reporting.context import ReportContextBuilder
from pathfinder.reporting.enums import RecommendationTemplateVersion
from pathfinder.reporting.input_models import RecommendationReportInputArtifact
from pathfinder.reporting.io import read_recommendation_report_input, write_recommendation_report
from pathfinder.reporting.models import LLMRecommendationItem, RecommendationItem, RecommendationPathOverview, RecommendationReportArtifact, RecommendationReportDiagnostics, RecommendationReportSummary
from pathfinder.reporting.templates import RecommendationTemplateRegistry


class RecommendationReportRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_path: Path
    output_path: Path
    template_version: RecommendationTemplateVersion = RecommendationTemplateVersion.V1
    max_files: int = 8
    max_file_chars: int = 4000
    timeout_seconds: float = 60.0


@dataclass(slots=True)
class RecommendationReportResult:
    artifact: RecommendationReportArtifact
    output_path: Path
    duration_seconds: float


class RecommendationReportService:
    def __init__(
        self,
        logger,
        *,
        llm_client,
        model: str,
        context_builder: ReportContextBuilder | None = None,
        template_registry: RecommendationTemplateRegistry | None = None,
    ) -> None:
        self._logger = logger
        self._llm_client = llm_client
        self._model = model
        self._context_builder = context_builder or ReportContextBuilder(logger)
        self._template_registry = template_registry or RecommendationTemplateRegistry()

    def run(self, request: RecommendationReportRequest) -> RecommendationReportResult:
        started = perf_counter()
        log_event(
            self._logger,
            "recommendation_report.started",
            fields={
                "input_path": str(request.input_path),
                "output_path": str(request.output_path),
                "template_version": request.template_version.value,
                "model": self._model,
                "max_files": request.max_files,
                "max_file_chars": request.max_file_chars,
            },
        )
        input_artifact = read_recommendation_report_input(request.input_path)
        context_bundle = self._context_builder.build(
            input_artifact,
            max_files=request.max_files,
            max_file_chars=request.max_file_chars,
        )
        template = self._template_registry.resolve(request.template_version)
        prompt = template.render(input_artifact, context_bundle)
        llm_result = self._llm_client.generate(
            StructuredLLMRequest(
                provider=LLMProvider.OPENROUTER,
                model=self._model,
                operation_name="recommendation_report.generate",
                response_format_name=self._template_registry.response_model().__name__,
                prompt=prompt,
                timeout_seconds=request.timeout_seconds,
                metadata={
                    "path_id": input_artifact.path_id,
                    "template_version": request.template_version.value,
                },
            ),
            response_model=self._template_registry.response_model(),
        )
        artifact = self._build_artifact(
            input_artifact=input_artifact,
            template_version=request.template_version,
            context_bundle=context_bundle,
            llm_payload=llm_result.parsed_output,
            llm_invocation=llm_result.invocation,
        )
        write_recommendation_report(artifact, request.output_path)
        duration = perf_counter() - started
        log_event(
            self._logger,
            "recommendation_report.completed",
            fields={
                "input_path": str(request.input_path),
                "output_path": str(request.output_path),
                "report_id": artifact.report_id,
                "path_id": input_artifact.path_id,
                "recommendation_count": artifact.summary.recommendation_count,
                "citation_count": artifact.summary.citation_count,
                "duration_seconds": round(duration, 6),
            },
        )
        return RecommendationReportResult(artifact=artifact, output_path=request.output_path, duration_seconds=duration)

    def _build_artifact(
        self,
        *,
        input_artifact: RecommendationReportInputArtifact,
        template_version: RecommendationTemplateVersion,
        context_bundle,
        llm_payload,
        llm_invocation,
    ) -> RecommendationReportArtifact:
        recommendations = [self._recommendation_from_llm_item(index=index, item=item) for index, item in enumerate(llm_payload.recommendations, start=1)]
        known_file_paths = self._known_file_paths(input_artifact)
        citation_count = self._citation_count(recommendations)
        return RecommendationReportArtifact(
            report_id=f"rr:{input_artifact.path_id}:{template_version.value}",
            template_version=template_version,
            input_artifact_id=input_artifact.input_artifact_id,
            repo_path=input_artifact.repo_path,
            known_file_paths=known_file_paths,
            path_overview=RecommendationPathOverview(
                path_id=input_artifact.path_id,
                ordered_node_ids=[node.id for node in input_artifact.path_nodes],
                ordered_edge_ids=[edge.id for edge in input_artifact.path_edges],
                ordered_file_paths=[node.path for node in input_artifact.path_nodes],
                path_narrative=llm_payload.path_narrative,
                target_rationale=llm_payload.target_rationale,
                top_priority_file_path=llm_payload.top_priority_file_path,
                top_priority_rationale=llm_payload.top_priority_rationale,
            ),
            recommendations=recommendations,
            llm_invocation=llm_invocation,
            summary=RecommendationReportSummary(
                path_node_count=len(input_artifact.path_nodes),
                path_edge_count=len(input_artifact.path_edges),
                known_file_count=len(known_file_paths),
                loaded_file_count=context_bundle.summary.loaded_file_count,
                missing_file_count=context_bundle.summary.missing_file_count,
                truncated_file_count=context_bundle.summary.truncated_file_count,
                dropped_file_count=context_bundle.summary.dropped_file_count,
                recommendation_count=len(recommendations),
                citation_count=citation_count,
            ),
            diagnostics=RecommendationReportDiagnostics(
                missing_file_paths=context_bundle.missing_file_paths,
                truncated_file_paths=context_bundle.truncated_file_paths,
                dropped_file_paths=context_bundle.dropped_file_paths,
                total_prompt_chars=context_bundle.summary.total_prompt_chars,
            ),
        )

    def _known_file_paths(self, input_artifact: RecommendationReportInputArtifact) -> list[str]:
        seen: set[str] = set()
        ordered_paths: list[str] = []
        for path in [node.path for node in input_artifact.path_nodes] + [item.path for item in input_artifact.focal_files]:
            if path in seen:
                continue
            seen.add(path)
            ordered_paths.append(path)
        return ordered_paths

    def _citation_count(self, recommendations: list[RecommendationItem]) -> int:
        return sum(
            1 + len(item.supporting_file_paths) + len(item.supporting_node_ids) + len(item.supporting_edge_ids)
            for item in recommendations
        )

    def _recommendation_from_llm_item(self, *, index: int, item: LLMRecommendationItem) -> RecommendationItem:
        return RecommendationItem(
            id=f"recommendation:{index}",
            priority=item.priority,
            title=item.title,
            summary=item.summary,
            mitigation_steps=item.mitigation_steps,
            primary_file_path=item.primary_file_path,
            supporting_file_paths=item.supporting_file_paths,
            supporting_node_ids=item.supporting_node_ids,
            supporting_edge_ids=item.supporting_edge_ids,
            confidence=item.confidence,
        )


def create_openrouter_recommendation_report_service(
    logger,
    *,
    model_override: str | None = None,
    timeout_seconds: float = 60.0,
) -> RecommendationReportService:
    settings = OpenRouterSettings.from_env(model_override=model_override, timeout_seconds=timeout_seconds)
    llm_client = OpenAIStructuredLLMClient(logger, settings)
    return RecommendationReportService(logger, llm_client=llm_client, model=settings.model)