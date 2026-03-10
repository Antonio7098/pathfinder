"""Recommendation reporting subsystem."""

from typing import TYPE_CHECKING, Any

from pathfinder.reporting.enums import RecommendationPriority, RecommendationReportVersion, RecommendationTemplateVersion
from pathfinder.reporting.input_models import RecommendationReportInputArtifact
from pathfinder.reporting.models import RecommendationReportArtifact

if TYPE_CHECKING:
    from pathfinder.reporting.service import RecommendationReportRequest, RecommendationReportResult, RecommendationReportService, create_openrouter_recommendation_report_service

__all__ = [
    "RecommendationPriority",
    "RecommendationReportArtifact",
    "RecommendationReportInputArtifact",
    "RecommendationReportRequest",
    "RecommendationReportResult",
    "RecommendationReportService",
    "RecommendationReportVersion",
    "RecommendationTemplateVersion",
    "create_openrouter_recommendation_report_service",
]


def __getattr__(name: str) -> Any:
    if name in {
        "RecommendationReportRequest",
        "RecommendationReportResult",
        "RecommendationReportService",
        "create_openrouter_recommendation_report_service",
    }:
        from pathfinder.reporting.service import RecommendationReportRequest, RecommendationReportResult, RecommendationReportService, create_openrouter_recommendation_report_service

        exports = {
            "RecommendationReportRequest": RecommendationReportRequest,
            "RecommendationReportResult": RecommendationReportResult,
            "RecommendationReportService": RecommendationReportService,
            "create_openrouter_recommendation_report_service": create_openrouter_recommendation_report_service,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")