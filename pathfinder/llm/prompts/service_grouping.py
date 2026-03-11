"""Centralized versioned prompts for service grouping."""

from __future__ import annotations

from dataclasses import dataclass

from pathfinder.llm.prompts.base import VersionedPromptRegistry
from pathfinder.llm.prompts.service_grouping_v1 import SERVICE_GROUPING_V1_TEMPLATE
from pathfinder.services.graphcode_context import ServiceGroupingGraphcodeEvidence
from pathfinder.services.enums import ServiceTemplateVersion
from pathfinder.services.models import LLMServiceGroupingPayload
from pathfinder.structural.models import StructuralGraphArtifact


@dataclass(frozen=True, slots=True)
class ServiceGroupingPromptContext:
    structural_graph: StructuralGraphArtifact
    graphcode_evidence: ServiceGroupingGraphcodeEvidence


class ServiceGroupingPromptRegistry(VersionedPromptRegistry[ServiceTemplateVersion, ServiceGroupingPromptContext]):
    def __init__(self) -> None:
        super().__init__(
            registry_name="service_grouping",
            templates={ServiceTemplateVersion.V1: SERVICE_GROUPING_V1_TEMPLATE},
        )

    @staticmethod
    def response_model() -> type[LLMServiceGroupingPayload]:
        return LLMServiceGroupingPayload