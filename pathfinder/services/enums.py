"""Typed enums for service grouping and service graph artifacts."""

from enum import StrEnum


class ServiceGroupingVersion(StrEnum):
    V1 = "service-grouping-artifact-v1"


class ServiceGraphVersion(StrEnum):
    V1 = "service-graph-artifact-v1"


class ServiceTemplateVersion(StrEnum):
    V1 = "service-grouping-v1"


class ServiceLayer(StrEnum):
    EDGE = "edge"
    APPLICATION = "application"
    DOMAIN = "domain"
    DATA = "data"
    SHARED = "shared"
    UNKNOWN = "unknown"


class ServiceKind(StrEnum):
    INFERRED = "inferred"
    DETERMINISTIC_CLUSTER = "deterministic_cluster"
    SHARED_BUCKET = "shared_bucket"
    UNCLASSIFIED_BUCKET = "unclassified_bucket"


class ServiceAssignmentKind(StrEnum):
    PRIMARY = "primary"
    SHARED = "shared"
    UNCLASSIFIED = "unclassified"


class ServiceResolutionSource(StrEnum):
    LLM_PRIMARY = "llm_primary"
    EXPLICIT_SHARED = "explicit_shared"
    EXPLICIT_UNCLASSIFIED = "explicit_unclassified"
    OVERLAP_SHARED = "overlap_shared"
    CONNECTIVITY_PRIMARY = "connectivity_primary"
    DIRECTORY_PRIMARY = "directory_primary"
    CLUSTER_PRIMARY = "cluster_primary"
    FALLBACK_UNCLASSIFIED = "fallback_unclassified"