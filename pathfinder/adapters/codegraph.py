"""CodeGraph adapter that isolates UCP integration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.adapters.codegraph_models import CodeGraphDocument
from pathfinder.errors import ExtractionError, PersistenceError, RepositoryAccessError
from pathfinder.observability.logging import log_event


class CodeGraphProtocol(Protocol):
    def to_json(self) -> str: ...
    def save(self, path: str) -> None: ...


class CodeGraphBuildConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_path: Path
    commit_hash: str | None = None
    include_hidden: bool = False
    continue_on_parse_error: bool = True
    max_file_bytes: int | None = None
    emit_export_edges: bool = True
    include_extensions: list[str] | None = None
    exclude_dirs: list[str] = Field(
        default_factory=lambda: [
            ".git",
            "target",
            "node_modules",
            "dist",
            "build",
            "__pycache__",
            ".venv",
            "venv",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".tox",
            ".next",
            ".turbo",
            "coverage",
        ]
    )


@dataclass(slots=True)
class CodeGraphBuildResult:
    graph: CodeGraphProtocol
    document: CodeGraphDocument
    duration_seconds: float


class CodeGraphAdapter:
    def __init__(self, logger) -> None:
        self._logger = logger

    def build(self, config: CodeGraphBuildConfig) -> CodeGraphBuildResult:
        repo_path = config.repo_path.resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            raise RepositoryAccessError("Repository path does not exist or is not a directory", context={"repo_path": str(repo_path)})

        try:
            import ucp
        except Exception as exc:  # pragma: no cover - import errors are environment-specific
            raise ExtractionError("Failed to import ucp / CodeGraph runtime", context={"repo_path": str(repo_path), "cause": str(exc)}) from exc

        log_event(self._logger, "codegraph.build.started", fields={"repo_path": str(repo_path)})
        started = perf_counter()
        try:
            graph = ucp.CodeGraph.build(
                str(repo_path),
                commit_hash=config.commit_hash,
                include_hidden=config.include_hidden,
                continue_on_parse_error=config.continue_on_parse_error,
                max_file_bytes=config.max_file_bytes,
                emit_export_edges=config.emit_export_edges,
                include_extensions=config.include_extensions,
                exclude_dirs=config.exclude_dirs,
            )
            document = CodeGraphDocument.model_validate(json.loads(graph.to_json()))
        except Exception as exc:
            raise ExtractionError("Failed to build CodeGraph", context={"repo_path": str(repo_path), "cause": str(exc)}) from exc

        duration = perf_counter() - started
        log_event(
            self._logger,
            "codegraph.build.completed",
            fields={"repo_path": str(repo_path), "block_count": len(document.blocks), "duration_seconds": round(duration, 6)},
        )
        return CodeGraphBuildResult(graph=graph, document=document, duration_seconds=duration)

    def save_raw_graph(self, graph: CodeGraphProtocol, output_path: Path) -> None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            graph.save(str(output_path))
        except Exception as exc:
            raise PersistenceError("Failed to persist raw CodeGraph artifact", context={"output_path": str(output_path), "cause": str(exc)}) from exc
        log_event(self._logger, "codegraph.persisted", fields={"output_path": str(output_path)})


def read_raw_codegraph_document(input_path: Path) -> CodeGraphDocument:
    try:
        return CodeGraphDocument.model_validate_json(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PersistenceError("Failed to read raw CodeGraph artifact", context={"input_path": str(input_path), "cause": str(exc)}) from exc
