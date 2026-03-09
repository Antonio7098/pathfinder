"""End-to-end structural graph extraction service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict

from pathfinder.adapters.codegraph import CodeGraphAdapter, CodeGraphBuildConfig
from pathfinder.observability.logging import log_event
from pathfinder.structural.io import write_structural_graph
from pathfinder.structural.models import StructuralGraphArtifact
from pathfinder.structural.projector import StructuralGraphProjector


class StructuralExtractionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_path: Path
    output_path: Path
    raw_codegraph_output_path: Path | None = None
    include_hidden: bool = False
    continue_on_parse_error: bool = True
    max_file_bytes: int | None = None


@dataclass(slots=True)
class StructuralExtractionResult:
    artifact: StructuralGraphArtifact
    output_path: Path
    raw_codegraph_output_path: Path | None
    duration_seconds: float


class StructuralExtractionService:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._adapter = CodeGraphAdapter(logger)
        self._projector = StructuralGraphProjector(logger)

    def run(self, request: StructuralExtractionRequest) -> StructuralExtractionResult:
        started = perf_counter()
        log_event(self._logger, "structural_extraction.started", fields={"repo_path": str(request.repo_path), "output_path": str(request.output_path)})
        build_result = self._adapter.build(
            CodeGraphBuildConfig(
                repo_path=request.repo_path,
                include_hidden=request.include_hidden,
                continue_on_parse_error=request.continue_on_parse_error,
                max_file_bytes=request.max_file_bytes,
            )
        )
        if request.raw_codegraph_output_path is not None:
            self._adapter.save_raw_graph(build_result.graph, request.raw_codegraph_output_path)
        artifact = self._projector.project(build_result.document, repo_path=request.repo_path.resolve())
        write_structural_graph(artifact, request.output_path)
        duration = perf_counter() - started
        log_event(
            self._logger,
            "structural_extraction.completed",
            fields={
                "repo_path": str(request.repo_path),
                "output_path": str(request.output_path),
                "raw_codegraph_output_path": str(request.raw_codegraph_output_path) if request.raw_codegraph_output_path else None,
                "file_count": artifact.summary.file_count,
                "structural_edge_count": artifact.summary.structural_edge_count,
                "duration_seconds": round(duration, 6),
            },
        )
        return StructuralExtractionResult(
            artifact=artifact,
            output_path=request.output_path,
            raw_codegraph_output_path=request.raw_codegraph_output_path,
            duration_seconds=duration,
        )
