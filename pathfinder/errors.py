"""Typed Pathfinder error taxonomy."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum


class ErrorCategory(StrEnum):
    CONFIGURATION = "configuration_error"
    REPOSITORY_ACCESS = "repository_access_error"
    EXTRACTION = "extraction_error"
    PROJECTION = "projection_error"
    VALIDATION = "validation_error"
    PERSISTENCE = "persistence_error"
    INTERNAL_INVARIANT = "internal_invariant_violation"


class PathfinderError(Exception):
    """Base typed exception for Pathfinder failures."""

    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory,
        context: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.context = dict(context or {})

    def __str__(self) -> str:
        if not self.context:
            return f"{self.category}: {self.message}"
        return f"{self.category}: {self.message} | context={self.context}"


class ConfigurationError(PathfinderError):
    def __init__(self, message: str, *, context: Mapping[str, object] | None = None) -> None:
        super().__init__(message, category=ErrorCategory.CONFIGURATION, context=context)


class RepositoryAccessError(PathfinderError):
    def __init__(self, message: str, *, context: Mapping[str, object] | None = None) -> None:
        super().__init__(message, category=ErrorCategory.REPOSITORY_ACCESS, context=context)


class ExtractionError(PathfinderError):
    def __init__(self, message: str, *, context: Mapping[str, object] | None = None) -> None:
        super().__init__(message, category=ErrorCategory.EXTRACTION, context=context)


class ProjectionError(PathfinderError):
    def __init__(self, message: str, *, context: Mapping[str, object] | None = None) -> None:
        super().__init__(message, category=ErrorCategory.PROJECTION, context=context)


class ValidationError(PathfinderError):
    def __init__(self, message: str, *, context: Mapping[str, object] | None = None) -> None:
        super().__init__(message, category=ErrorCategory.VALIDATION, context=context)


class PersistenceError(PathfinderError):
    def __init__(self, message: str, *, context: Mapping[str, object] | None = None) -> None:
        super().__init__(message, category=ErrorCategory.PERSISTENCE, context=context)


class InternalInvariantError(PathfinderError):
    def __init__(self, message: str, *, context: Mapping[str, object] | None = None) -> None:
        super().__init__(message, category=ErrorCategory.INTERNAL_INVARIANT, context=context)
