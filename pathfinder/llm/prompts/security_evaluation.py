"""Centralized versioned prompts for security evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from pathfinder.llm.prompts.base import VersionedPromptRegistry
from pathfinder.llm.prompts.security_evaluation_v1 import EDGE_SECURITY_EVALUATION_V1_TEMPLATE, FILE_SECURITY_EVALUATION_V1_TEMPLATE
from pathfinder.security_evaluators.models import EdgeSecurityAnalysisPayload, FileSecurityAnalysisPayload


@dataclass(frozen=True, slots=True)
class FileSecurityPromptContext:
    file_path: str
    code: str


@dataclass(frozen=True, slots=True)
class EdgeSecurityPromptContext:
    structural_edge_id: str
    relationship_type: str
    source_path: str
    target_path: str
    source_code: str
    target_code: str
    valid_attack_types: tuple[str, ...]


class FileSecurityPromptRegistry(VersionedPromptRegistry[str, FileSecurityPromptContext]):
    def __init__(self) -> None:
        super().__init__(
            registry_name="file_security_evaluation",
            templates={"security-evaluation-v1": FILE_SECURITY_EVALUATION_V1_TEMPLATE},
        )

    @staticmethod
    def response_model() -> type[FileSecurityAnalysisPayload]:
        return FileSecurityAnalysisPayload


class EdgeSecurityPromptRegistry(VersionedPromptRegistry[str, EdgeSecurityPromptContext]):
    def __init__(self) -> None:
        super().__init__(
            registry_name="edge_security_evaluation",
            templates={"security-evaluation-v1": EDGE_SECURITY_EVALUATION_V1_TEMPLATE},
        )

    @staticmethod
    def response_model() -> type[EdgeSecurityAnalysisPayload]:
        return EdgeSecurityAnalysisPayload
