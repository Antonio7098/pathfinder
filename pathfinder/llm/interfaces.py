"""Provider-agnostic interfaces for structured LLM execution."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

from pathfinder.llm.models import StructuredLLMRequest, StructuredLLMResult


StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


class StructuredLLMClient(Protocol):
    def generate(
        self,
        request: StructuredLLMRequest,
        *,
        response_model: type[StructuredOutputT],
    ) -> StructuredLLMResult[StructuredOutputT]: ...