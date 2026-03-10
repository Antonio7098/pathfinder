"""Typed enums for recommendation reporting artifacts."""

from enum import StrEnum


class RecommendationInputVersion(StrEnum):
    V1 = "recommendation-input-v1"


class RecommendationReportVersion(StrEnum):
    V1 = "recommendation-report-artifact-v1"


class RecommendationTemplateVersion(StrEnum):
    V1 = "recommendation-report-v1"


class RecommendationPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"