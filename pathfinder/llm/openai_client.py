"""OpenAI SDK adapter configured for OpenRouter structured calls."""

from __future__ import annotations

from time import perf_counter
from typing import Any, TypeVar

from openai import OpenAI

from pathfinder.errors import ExternalDependencyError, ValidationError
from pathfinder.llm.config import OpenRouterSettings
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredLLMRequest, StructuredLLMResult, TokenUsage
from pathfinder.observability.logging import log_event


StructuredOutputT = TypeVar("StructuredOutputT")


class OpenAIStructuredLLMClient:
    def __init__(self, logger, config: OpenRouterSettings, *, client: Any | None = None) -> None:
        self._logger = logger
        self._config = config
        self._client = client or OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=config.timeout_seconds)

    def generate(self, request: StructuredLLMRequest, *, response_model: type[StructuredOutputT]) -> StructuredLLMResult[StructuredOutputT]:
        log_event(
            self._logger,
            "llm.request.started",
            fields={
                "provider": request.provider.value,
                "base_url": self._config.base_url,
                "model": request.model,
                "operation_name": request.operation_name,
                "response_format_name": request.response_format_name,
                "template_version": request.prompt.template_version,
                "prompt_version": request.prompt.prompt_version,
                "system_prompt_sha256": request.prompt.system_prompt_sha256,
                "user_prompt_sha256": request.prompt.user_prompt_sha256,
                "system_prompt_chars": len(request.prompt.system_prompt),
                "user_prompt_chars": len(request.prompt.user_prompt),
                "max_output_tokens": request.max_output_tokens,
                "temperature": request.temperature,
                "timeout_seconds": request.timeout_seconds,
            },
        )
        log_event(
            self._logger,
            "llm.request.prompt",
            level=10,
            fields={
                "provider": request.provider.value,
                "operation_name": request.operation_name,
                "template_version": request.prompt.template_version,
                "prompt_version": request.prompt.prompt_version,
                "system_prompt": request.prompt.system_prompt,
                "user_prompt": request.prompt.user_prompt,
            },
        )

        started = perf_counter()
        try:
            response = self._client.beta.chat.completions.parse(
                model=request.model,
                messages=[
                    {"role": "system", "content": request.prompt.system_prompt},
                    {"role": "user", "content": request.prompt.user_prompt},
                ],
                response_format=response_model,
                temperature=request.temperature,
                max_completion_tokens=request.max_output_tokens,
                metadata=request.metadata or None,
                store=False,
                extra_headers={"X-Title": self._config.app_name},
                timeout=request.timeout_seconds,
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            raise ExternalDependencyError(
                "Structured LLM request failed",
                context={
                    "provider": request.provider.value,
                    "base_url": self._config.base_url,
                    "model": request.model,
                    "operation_name": request.operation_name,
                    "status_code": status_code,
                    "cause": str(exc),
                },
            ) from exc

        parsed = self._extract_parsed_output(response)
        duration = perf_counter() - started
        usage = self._extract_usage(response)
        finish_reason = self._extract_finish_reason(response)
        provider_request_id = getattr(response, "id", None)

        invocation = LLMInvocationRecord(
            provider=LLMProvider.OPENROUTER,
            base_url=self._config.base_url,
            model=getattr(response, "model", request.model),
            operation_name=request.operation_name,
            response_format_name=request.response_format_name,
            template_version=request.prompt.template_version,
            prompt_version=request.prompt.prompt_version,
            system_prompt=request.prompt.system_prompt,
            user_prompt=request.prompt.user_prompt,
            system_prompt_sha256=request.prompt.system_prompt_sha256,
            user_prompt_sha256=request.prompt.user_prompt_sha256,
            system_prompt_chars=len(request.prompt.system_prompt),
            user_prompt_chars=len(request.prompt.user_prompt),
            provider_request_id=provider_request_id,
            finish_reason=finish_reason,
            usage=usage,
            duration_seconds=round(duration, 6),
        )
        log_event(
            self._logger,
            "llm.request.completed",
            fields={
                "provider": request.provider.value,
                "base_url": self._config.base_url,
                "model": invocation.model,
                "operation_name": request.operation_name,
                "provider_request_id": provider_request_id,
                "finish_reason": finish_reason,
                "input_tokens": usage.input_tokens if usage else None,
                "output_tokens": usage.output_tokens if usage else None,
                "total_tokens": usage.total_tokens if usage else None,
                "duration_seconds": invocation.duration_seconds,
            },
        )
        return StructuredLLMResult(parsed_output=parsed, invocation=invocation)

    def _extract_parsed_output(self, response: Any) -> StructuredOutputT:
        choices = getattr(response, "choices", None) or []
        parsed = getattr(choices[0].message, "parsed", None) if choices else None
        if parsed is None:
            refusal = getattr(choices[0].message, "refusal", None) if choices else None
            raise ValidationError(
                "Structured LLM response did not contain a parsed payload",
                context={"provider_request_id": getattr(response, "id", None), "refusal": refusal},
            )
        return parsed

    def _extract_finish_reason(self, response: Any) -> str | None:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return None
        return getattr(choices[0], "finish_reason", None)

    def _extract_usage(self, response: Any) -> TokenUsage | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        return TokenUsage(
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )
