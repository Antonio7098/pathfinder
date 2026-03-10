"""Centralized versioned prompts for recommendation reporting."""

from __future__ import annotations

from dataclasses import dataclass

from pathfinder.llm.prompts.base import VersionedPromptRegistry
from pathfinder.llm.prompts.recommendation_report_v1 import RECOMMENDATION_REPORT_V1_TEMPLATE
from pathfinder.reporting.context import ReportContextBundle
from pathfinder.reporting.enums import RecommendationTemplateVersion
from pathfinder.reporting.input_models import RecommendationReportInputArtifact
from pathfinder.reporting.models import LLMRecommendationReportPayload


@dataclass(frozen=True, slots=True)
class RecommendationReportPromptContext:
    input_artifact: RecommendationReportInputArtifact
    context_bundle: ReportContextBundle


class RecommendationReportPromptRegistry(VersionedPromptRegistry[RecommendationTemplateVersion, RecommendationReportPromptContext]):
    def __init__(self) -> None:
        super().__init__(
            registry_name="recommendation_report",
            templates={RecommendationTemplateVersion.V1: RECOMMENDATION_REPORT_V1_TEMPLATE},
        )

    @staticmethod
    def response_model() -> type[LLMRecommendationReportPayload]:
        return LLMRecommendationReportPayload