"""Typed request and result models for the full Pathfinder pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FullPipelineRequest:
    repo_path: Path
    output_dir: Path
    graph_mode: str = "service"
    provider: str = "openrouter"
    model: str | None = None
    include_hidden: bool = False
    strict_parse: bool = False
    timeout_seconds: float = 60.0
    max_files: int = 8
    max_file_chars: int = 4000
    max_output_tokens: int = 8192


@dataclass(frozen=True, slots=True)
class FullPipelineResult:
    structural_graph_path: Path
    raw_codegraph_path: Path
    service_grouping_path: Path
    service_graph_path: Path
    security_graph_path: Path
    selected_path_input_path: Path
    recommendation_report_path: Path
    dashboard_path: Path
