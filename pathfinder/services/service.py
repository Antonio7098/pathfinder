"""Service grouping and service graph orchestration services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict

from pathfinder.adapters.codegraph import read_raw_codegraph_document
from pathfinder.llm import LLMProvider, MiniMaxSettings, MiniMaxStructuredLLMClient, OpenAIStructuredLLMClient, OpenRouterSettings, StructuredLLMRequest
from pathfinder.llm.prompts.service_grouping import ServiceGroupingPromptContext, ServiceGroupingPromptRegistry
from pathfinder.observability.logging import log_event
from pathfinder.services.enums import ServiceTemplateVersion
from pathfinder.services.graphcode_context import ServiceGroupingGraphcodeContextBuilder
from pathfinder.services.graph_builder import ServiceGraphBuilder
from pathfinder.services.io import read_service_grouping, write_service_graph, write_service_grouping
from pathfinder.services.models import ServiceGraphArtifact, ServiceGroupingArtifact
from pathfinder.services.resolver import ServiceGroupingResolver
from pathfinder.structural.io import read_structural_graph


class ServiceGroupingRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_path: Path
    output_path: Path
    raw_codegraph_input_path: Path | None = None
    template_version: ServiceTemplateVersion = ServiceTemplateVersion.V1
    timeout_seconds: float = 60.0
    max_output_tokens: int = 8192


@dataclass(slots=True)
class ServiceGroupingResult:
    artifact: ServiceGroupingArtifact
    output_path: Path
    duration_seconds: float


class ServiceGraphRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    structural_graph_path: Path
    grouping_path: Path
    output_path: Path


@dataclass(slots=True)
class ServiceGraphResult:
    artifact: ServiceGraphArtifact
    output_path: Path
    duration_seconds: float


class ServiceGroupingService:
    def __init__(
        self,
        logger,
        *,
        llm_client,
        model: str,
        provider: LLMProvider = LLMProvider.OPENROUTER,
        prompt_registry: ServiceGroupingPromptRegistry | None = None,
        resolver: ServiceGroupingResolver | None = None,
        graphcode_context_builder: ServiceGroupingGraphcodeContextBuilder | None = None,
    ) -> None:
        self._logger = logger
        self._llm_client = llm_client
        self._model = model
        self._provider = provider
        self._prompt_registry = prompt_registry or ServiceGroupingPromptRegistry()
        self._resolver = resolver or ServiceGroupingResolver()
        self._graphcode_context_builder = graphcode_context_builder or ServiceGroupingGraphcodeContextBuilder()

    def run(self, request: ServiceGroupingRequest) -> ServiceGroupingResult:
        started = perf_counter()
        log_event(
            self._logger,
            "service_grouping.started",
            fields={
                "input_path": str(request.input_path),
                "output_path": str(request.output_path),
                "raw_codegraph_input_path": str(request.raw_codegraph_input_path) if request.raw_codegraph_input_path else None,
                "template_version": request.template_version.value,
                "model": self._model,
            },
        )
        structural_graph = read_structural_graph(request.input_path)
        raw_codegraph = read_raw_codegraph_document(request.raw_codegraph_input_path) if request.raw_codegraph_input_path is not None else None
        graphcode_evidence = self._graphcode_context_builder.build(structural_graph=structural_graph, raw_codegraph=raw_codegraph)
        prompt_template = self._prompt_registry.resolve(request.template_version)
        prompt = prompt_template.render(ServiceGroupingPromptContext(structural_graph=structural_graph, graphcode_evidence=graphcode_evidence))
        llm_result = self._llm_client.generate(
            StructuredLLMRequest(
                provider=self._provider,
                model=self._model,
                operation_name="service_grouping.generate",
                response_format_name=self._prompt_registry.response_model().__name__,
                prompt=prompt,
                timeout_seconds=request.timeout_seconds,
                max_output_tokens=request.max_output_tokens,
                metadata={"graph_id": structural_graph.graph_id, "template_version": request.template_version.value},
            ),
            response_model=self._prompt_registry.response_model(),
        )
        artifact = self._resolver.resolve(
            structural_graph=structural_graph,
            payload=llm_result.parsed_output,
            template_version=request.template_version,
            llm_invocation=llm_result.invocation,
        )
        write_service_grouping(artifact, request.output_path)
        duration = perf_counter() - started
        log_event(
            self._logger,
            "service_grouping.completed",
            fields={
                "input_path": str(request.input_path),
                "output_path": str(request.output_path),
                "grouping_id": artifact.grouping_id,
                "service_count": artifact.summary.service_count,
                "file_count": artifact.summary.file_count,
                "ambiguous_file_count": artifact.summary.ambiguous_file_count,
                "graphcode_available": graphcode_evidence.available,
                "graphcode_symbol_block_count": graphcode_evidence.symbol_block_count,
                "duration_seconds": round(duration, 6),
            },
        )
        return ServiceGroupingResult(artifact=artifact, output_path=request.output_path, duration_seconds=duration)


class ServiceGraphService:
    def __init__(self, logger, *, builder: ServiceGraphBuilder | None = None) -> None:
        self._logger = logger
        self._builder = builder or ServiceGraphBuilder()

    def run(self, request: ServiceGraphRequest) -> ServiceGraphResult:
        started = perf_counter()
        log_event(
            self._logger,
            "service_graph.started",
            fields={
                "structural_graph_path": str(request.structural_graph_path),
                "grouping_path": str(request.grouping_path),
                "output_path": str(request.output_path),
            },
        )
        structural_graph = read_structural_graph(request.structural_graph_path)
        grouping_artifact = read_service_grouping(request.grouping_path)
        artifact = self._builder.build(structural_graph=structural_graph, grouping_artifact=grouping_artifact)
        write_service_graph(artifact, request.output_path)
        duration = perf_counter() - started
        log_event(
            self._logger,
            "service_graph.completed",
            fields={
                "output_path": str(request.output_path),
                "service_graph_id": artifact.service_graph_id,
                "service_count": artifact.summary.service_count,
                "service_edge_count": artifact.summary.service_edge_count,
                "duration_seconds": round(duration, 6),
            },
        )
        return ServiceGraphResult(artifact=artifact, output_path=request.output_path, duration_seconds=duration)


def create_openrouter_service_grouping_service(
    logger,
    *,
    model_override: str | None = None,
    timeout_seconds: float = 60.0,
) -> ServiceGroupingService:
    settings = OpenRouterSettings.from_env(model_override=model_override, timeout_seconds=timeout_seconds)
    llm_client = OpenAIStructuredLLMClient(logger, settings)
    return ServiceGroupingService(logger, llm_client=llm_client, model=settings.model, provider=LLMProvider.OPENROUTER)


def create_minimax_service_grouping_service(
    logger,
    *,
    model_override: str | None = None,
    timeout_seconds: float = 60.0,
) -> ServiceGroupingService:
    settings = MiniMaxSettings.from_env(model_override=model_override, timeout_seconds=timeout_seconds)
    llm_client = MiniMaxStructuredLLMClient(logger, settings)
    return ServiceGroupingService(logger, llm_client=llm_client, model=settings.model, provider=LLMProvider.MINIMAX)
