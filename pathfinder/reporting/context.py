"""Deterministic file-context collection for recommendation reports."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.llm.prompt_injection import scan_prompt_injection_signals, wrap_untrusted_repository_text
from pathfinder.observability.logging import log_event
from pathfinder.reporting.input_models import RecommendationReportInputArtifact


class ReportFileContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    content: str
    missing: bool = False
    truncated: bool = False
    original_char_count: int = 0
    included_char_count: int = 0
    prompt_injection_signal_count: int = 0
    prompt_injection_signals: list[str] = Field(default_factory=list)


class ReportContextSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    requested_file_count: int
    included_file_count: int
    loaded_file_count: int
    missing_file_count: int
    truncated_file_count: int
    dropped_file_count: int
    total_prompt_chars: int
    suspicious_file_count: int = 0
    prompt_injection_signal_count: int = 0


class ReportContextBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    files: list[ReportFileContext]
    missing_file_paths: list[str] = Field(default_factory=list)
    truncated_file_paths: list[str] = Field(default_factory=list)
    dropped_file_paths: list[str] = Field(default_factory=list)
    suspicious_file_paths: list[str] = Field(default_factory=list)
    summary: ReportContextSummary


class ReportContextBuilder:
    def __init__(self, logger) -> None:
        self._logger = logger

    def build(
        self,
        input_artifact: RecommendationReportInputArtifact,
        *,
        max_files: int,
        max_file_chars: int,
    ) -> ReportContextBundle:
        path_file_paths = [node.path for node in input_artifact.path_nodes]
        extra_file_paths = sorted(reference.path for reference in input_artifact.focal_files if reference.path not in set(path_file_paths))
        requested_paths = path_file_paths + extra_file_paths
        included_paths = requested_paths[:max_files]
        dropped_paths = requested_paths[max_files:]

        files: list[ReportFileContext] = []
        missing_file_paths: list[str] = []
        truncated_file_paths: list[str] = []
        suspicious_file_paths: list[str] = []
        total_prompt_chars = 0
        prompt_injection_signal_count = 0
        repo_path = Path(input_artifact.repo_path)

        for relative_path in included_paths:
            absolute_path = repo_path / relative_path
            if not absolute_path.exists() or not absolute_path.is_file():
                missing_file_paths.append(relative_path)
                files.append(ReportFileContext(path=relative_path, content="", missing=True))
                continue
            raw_content = absolute_path.read_text(encoding="utf-8", errors="replace")
            signal_scan = scan_prompt_injection_signals(raw_content)
            truncated = len(raw_content) > max_file_chars
            rendered_content = wrap_untrusted_repository_text(
                raw_content[:max_file_chars],
                source_label=relative_path,
                signal_scan=signal_scan,
            )
            if truncated:
                truncated_file_paths.append(relative_path)
            if signal_scan.signal_count > 0:
                suspicious_file_paths.append(relative_path)
                prompt_injection_signal_count += signal_scan.signal_count
            total_prompt_chars += len(rendered_content)
            files.append(
                ReportFileContext(
                    path=relative_path,
                    content=rendered_content,
                    truncated=truncated,
                    original_char_count=len(raw_content),
                    included_char_count=len(raw_content[:max_file_chars]),
                    prompt_injection_signal_count=signal_scan.signal_count,
                    prompt_injection_signals=list(signal_scan.matched_signals),
                )
            )

        bundle = ReportContextBundle(
            files=files,
            missing_file_paths=missing_file_paths,
            truncated_file_paths=truncated_file_paths,
            dropped_file_paths=dropped_paths,
            suspicious_file_paths=suspicious_file_paths,
            summary=ReportContextSummary(
                requested_file_count=len(requested_paths),
                included_file_count=len(included_paths),
                loaded_file_count=sum(1 for item in files if not item.missing),
                missing_file_count=len(missing_file_paths),
                truncated_file_count=len(truncated_file_paths),
                dropped_file_count=len(dropped_paths),
                total_prompt_chars=total_prompt_chars,
                suspicious_file_count=len(suspicious_file_paths),
                prompt_injection_signal_count=prompt_injection_signal_count,
            ),
        )
        log_event(
            self._logger,
            "recommendation_report.context.built",
            fields={
                "path_id": input_artifact.path_id,
                "requested_file_count": bundle.summary.requested_file_count,
                "included_file_count": bundle.summary.included_file_count,
                "loaded_file_count": bundle.summary.loaded_file_count,
                "missing_file_count": bundle.summary.missing_file_count,
                "truncated_file_count": bundle.summary.truncated_file_count,
                "dropped_file_count": bundle.summary.dropped_file_count,
                "suspicious_file_count": bundle.summary.suspicious_file_count,
                "prompt_injection_signal_count": bundle.summary.prompt_injection_signal_count,
                "total_prompt_chars": bundle.summary.total_prompt_chars,
            },
        )
        return bundle