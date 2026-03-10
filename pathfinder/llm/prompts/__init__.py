"""Centralized versioned prompt registries for Pathfinder."""

from typing import TYPE_CHECKING, Any

from pathfinder.llm.prompts.base import VersionedPromptRegistry, VersionedPromptTemplate, build_structured_prompt

if TYPE_CHECKING:
    from pathfinder.llm.prompts.recommendation_report import RecommendationReportPromptContext, RecommendationReportPromptRegistry
    from pathfinder.llm.prompts.recommendation_report_v1 import RECOMMENDATION_REPORT_V1_TEMPLATE

__all__ = [
    "RecommendationReportPromptContext",
    "RecommendationReportPromptRegistry",
    "RECOMMENDATION_REPORT_V1_TEMPLATE",
    "VersionedPromptRegistry",
    "VersionedPromptTemplate",
    "build_structured_prompt",
]


def __getattr__(name: str) -> Any:
    if name in {"RecommendationReportPromptContext", "RecommendationReportPromptRegistry"}:
        from pathfinder.llm.prompts.recommendation_report import RecommendationReportPromptContext, RecommendationReportPromptRegistry

        exports = {
            "RecommendationReportPromptContext": RecommendationReportPromptContext,
            "RecommendationReportPromptRegistry": RecommendationReportPromptRegistry,
        }
        return exports[name]
    if name == "RECOMMENDATION_REPORT_V1_TEMPLATE":
        from pathfinder.llm.prompts.recommendation_report_v1 import RECOMMENDATION_REPORT_V1_TEMPLATE

        return RECOMMENDATION_REPORT_V1_TEMPLATE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")