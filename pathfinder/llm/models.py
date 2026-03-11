"""Typed models shared by Pathfinder LLM integrations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class LLMProvider(StrEnum):
    OPENROUTER = "openrouter"
    MINIMAX = "minimax"


class StructuredPrompt(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_version: str
    prompt_version: str
    system_prompt: str
    user_prompt: str
    system_prompt_sha256: str
    user_prompt_sha256: str


class StructuredLLMRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: LLMProvider
    model: str
    operation_name: str
    response_format_name: str
    prompt: StructuredPrompt
    temperature: float = 0.0
    timeout_seconds: float = 60.0
    max_output_tokens: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class LLMInvocationRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: LLMProvider
    base_url: str
    model: str
    operation_name: str
    response_format_name: str
    template_version: str
    prompt_version: str
    system_prompt: str
    user_prompt: str
    system_prompt_sha256: str
    user_prompt_sha256: str
    system_prompt_chars: int
    user_prompt_chars: int
    provider_request_id: str | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    duration_seconds: float


StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


@dataclass(slots=True)
class StructuredLLMResult(Generic[StructuredOutputT]):
    parsed_output: StructuredOutputT
    invocation: LLMInvocationRecord
