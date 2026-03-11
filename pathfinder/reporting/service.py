"""Recommendation report orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict

from pathfinder.errors import ExternalDependencyError, ValidationError
from pathfinder.llm import LLMProvider, MiniMaxSettings, MiniMaxStructuredLLMClient, OpenAIStructuredLLMClient, OpenRouterSettings, StructuredLLMRequest
from pathfinder.llm.models import LLMInvocationRecord, TokenUsage
from pathfinder.llm.prompts.recommendation_report import RecommendationReportPromptContext, RecommendationReportPromptRegistry
from pathfinder.observability.logging import log_event
from pathfinder.reporting.context import ReportContextBuilder, ReportContextBundle
from pathfinder.reporting.enums import RecommendationPriority, RecommendationTemplateVersion
from pathfinder.reporting.input_models import RecommendationReportInputArtifact
from pathfinder.reporting.io import read_recommendation_report_input, write_recommendation_report
from pathfinder.reporting.models import LLMRecommendationItem, LLMRecommendationReportPayload, RecommendationItem, RecommendationPathOverview, RecommendationReportArtifact, RecommendationReportDiagnostics, RecommendationReportSummary


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
        provider: LLMProvider = LLMProvider.OPENROUTER,
        context_builder: ReportContextBuilder | None = None,
        prompt_registry: RecommendationReportPromptRegistry | None = None,
    ) -> None:
        self._logger = logger
        self._llm_client = llm_client
        self._model = model
        self._provider = provider
        self._context_builder = context_builder or ReportContextBuilder(logger)
        self._prompt_registry = prompt_registry or RecommendationReportPromptRegistry()

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
        prompt_template = self._prompt_registry.resolve(request.template_version)
        prompt = prompt_template.render(
            RecommendationReportPromptContext(
                input_artifact=input_artifact,
                context_bundle=context_bundle,
            )
        )
        llm_request = StructuredLLMRequest(
            provider=self._provider,
            model=self._model,
            operation_name="recommendation_report.generate",
            response_format_name=self._prompt_registry.response_model().__name__,
            prompt=prompt,
            timeout_seconds=request.timeout_seconds,
            metadata={
                "path_id": input_artifact.path_id,
                "template_version": request.template_version.value,
            },
        )
        try:
            llm_result = self._llm_client.generate(
                llm_request,
                response_model=self._prompt_registry.response_model(),
            )
            llm_payload = llm_result.parsed_output
            llm_invocation = llm_result.invocation
        except (ValidationError, ExternalDependencyError) as exc:
            if self._provider is not LLMProvider.MINIMAX:
                raise
            log_event(
                self._logger,
                "recommendation_report.fallback",
                fields={
                    "provider": self._provider.value,
                    "path_id": input_artifact.path_id,
                    "cause": str(exc),
                },
            )
            llm_payload = self._fallback_payload(input_artifact=input_artifact)
            llm_invocation = self._fallback_invocation(llm_request=llm_request, cause=exc)
        artifact = self._build_artifact(
            input_artifact=input_artifact,
            template_version=request.template_version,
            context_bundle=context_bundle,
            llm_payload=llm_payload,
            llm_invocation=llm_invocation,
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
        context_bundle: ReportContextBundle,
        llm_payload: LLMRecommendationReportPayload,
        llm_invocation: LLMInvocationRecord,
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

    def _fallback_payload(self, *, input_artifact: RecommendationReportInputArtifact) -> LLMRecommendationReportPayload:
        path_nodes = input_artifact.path_nodes
        path_edges = input_artifact.path_edges
        top_priority_node = max(
            path_nodes,
            key=lambda node: (
                node.target_flag,
                node.normalized_risk_score if node.normalized_risk_score is not None else -1.0,
                node.confidence if node.confidence is not None else -1.0,
            ),
        )
        recommendations: list[LLMRecommendationItem] = []
        path_length = len(path_nodes)
        for index, node in enumerate(path_nodes[:3]):
            role = node.role or ("target" if node.target_flag else "transition")
            edge_ids: list[str] = []
            node_ids = [node.id]
            supporting_paths = [candidate.path for candidate in path_nodes if candidate.path != node.path][:2]
            if index > 0:
                prior_edge = path_edges[index - 1]
                edge_ids.append(prior_edge.id)
                node_ids.insert(0, prior_edge.source)
            if index < len(path_edges):
                next_edge = path_edges[index]
                edge_ids.append(next_edge.id)
                if next_edge.target not in node_ids:
                    node_ids.append(next_edge.target)
            recommendations.append(
                LLMRecommendationItem(
                    priority=self._fallback_priority(index=index, path_length=path_length, target_flag=node.target_flag),
                    title=f"Review controls around {node.path}",
                    summary=(
                        f"Prioritize code review and hardening for the {role} file on the selected path. "
                        "This fallback recommendation was generated deterministically because the provider response was unavailable."
                    ),
                    mitigation_steps=[
                        f"Audit trust boundaries and input handling in {node.path}.",
                        f"Add focused tests that exercise attacker-controlled flows reaching {node.path}.",
                    ],
                    primary_file_path=node.path,
                    supporting_file_paths=supporting_paths,
                    supporting_node_ids=node_ids,
                    supporting_edge_ids=edge_ids,
                    confidence=0.0,
                )
            )
        return LLMRecommendationReportPayload(
            path_narrative=(
                f"The selected path traverses {len(path_nodes)} files and {len(path_edges)} grounded attack edges. "
                "This narrative was generated deterministically because the provider response was unavailable."
            ),
            target_rationale=(
                f"{path_nodes[-1].path} is the terminal file on the selected path"
                + (" and is marked as a target." if path_nodes[-1].target_flag else ".")
            ),
            top_priority_file_path=top_priority_node.path,
            top_priority_rationale=(
                f"{top_priority_node.path} was selected as the top priority because it is the highest-risk grounded file on the chosen path."
            ),
            recommendations=recommendations,
        )

    def _fallback_priority(self, *, index: int, path_length: int, target_flag: bool) -> RecommendationPriority:
        if target_flag:
            return RecommendationPriority.CRITICAL
        if index == 0:
            return RecommendationPriority.HIGH
        if index + 1 == path_length:
            return RecommendationPriority.HIGH
        return RecommendationPriority.MEDIUM

    def _fallback_invocation(self, *, llm_request: StructuredLLMRequest, cause: Exception) -> LLMInvocationRecord:
        provider_request_id = None
        if isinstance(cause, (ValidationError, ExternalDependencyError)):
            provider_request_id = str(cause.context.get("provider_request_id")) if cause.context.get("provider_request_id") is not None else None
        return LLMInvocationRecord(
            provider=llm_request.provider,
            base_url=self._llm_client._config.base_url,
            model=llm_request.model,
            operation_name=llm_request.operation_name,
            response_format_name=llm_request.response_format_name,
            template_version=llm_request.prompt.template_version,
            prompt_version=llm_request.prompt.prompt_version,
            system_prompt=llm_request.prompt.system_prompt,
            user_prompt=llm_request.prompt.user_prompt,
            system_prompt_sha256=llm_request.prompt.system_prompt_sha256,
            user_prompt_sha256=llm_request.prompt.user_prompt_sha256,
            system_prompt_chars=len(llm_request.prompt.system_prompt),
            user_prompt_chars=len(llm_request.prompt.user_prompt),
            provider_request_id=provider_request_id,
            finish_reason="fallback",
            usage=TokenUsage(),
            duration_seconds=0.0,
        )


def create_openrouter_recommendation_report_service(
    logger,
    *,
    model_override: str | None = None,
    timeout_seconds: float = 60.0,
) -> RecommendationReportService:
    settings = OpenRouterSettings.from_env(model_override=model_override, timeout_seconds=timeout_seconds)
    llm_client = OpenAIStructuredLLMClient(logger, settings)
    return RecommendationReportService(logger, llm_client=llm_client, model=settings.model, provider=LLMProvider.OPENROUTER)


def create_minimax_recommendation_report_service(
    logger,
    *,
    model_override: str | None = None,
    timeout_seconds: float = 60.0,
) -> RecommendationReportService:
    settings = MiniMaxSettings.from_env(model_override=model_override, timeout_seconds=timeout_seconds)
    llm_client = MiniMaxStructuredLLMClient(logger, settings)
    return RecommendationReportService(logger, llm_client=llm_client, model=settings.model, provider=LLMProvider.MINIMAX)
