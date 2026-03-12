"""Retrying wrapper for structured LLM clients."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import TypeVar
from urllib.error import HTTPError

from pydantic import BaseModel

from pathfinder.errors import ExternalDependencyError
from pathfinder.llm.interfaces import StructuredLLMClient
from pathfinder.llm.models import StructuredLLMRequest, StructuredLLMResult
from pathfinder.observability.logging import log_event


StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.5


class ResilientStructuredLLMClient:
    def __init__(
        self,
        logger,
        wrapped: StructuredLLMClient,
        *,
        retry_policy: RetryPolicy | None = None,
        sleep_func=time.sleep,
    ) -> None:
        self._logger = logger
        self._wrapped = wrapped
        self._config = getattr(wrapped, "_config", None)
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep_func

    def generate(
        self,
        request: StructuredLLMRequest,
        *,
        response_model: type[StructuredOutputT],
    ) -> StructuredLLMResult[StructuredOutputT]:
        last_error: ExternalDependencyError | None = None
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            try:
                return self._wrapped.generate(request, response_model=response_model)
            except ExternalDependencyError as exc:
                last_error = exc
                if not self._is_retryable(exc) or attempt >= self._retry_policy.max_attempts:
                    raise
                delay_seconds = self._delay_for_attempt(attempt)
                log_event(
                    self._logger,
                    "llm.request.retrying",
                    fields={
                        "provider": request.provider.value,
                        "model": request.model,
                        "operation_name": request.operation_name,
                        "attempt": attempt,
                        "max_attempts": self._retry_policy.max_attempts,
                        "delay_seconds": round(delay_seconds, 3),
                        "retry_reason": exc.context.get("status_code") or exc.context.get("cause"),
                    },
                )
                self._sleep(delay_seconds)
        assert last_error is not None
        raise last_error

    def _delay_for_attempt(self, attempt: int) -> float:
        exponential_delay = min(
            self._retry_policy.base_delay_seconds * (2 ** (attempt - 1)),
            self._retry_policy.max_delay_seconds,
        )
        jitter = random.uniform(0.0, self._retry_policy.jitter_seconds)
        return min(exponential_delay + jitter, self._retry_policy.max_delay_seconds)

    def _is_retryable(self, error: ExternalDependencyError) -> bool:
        status_code = self._coerce_status_code(error.context.get("status_code"))
        if status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
            return True
        cause = str(error.context.get("cause", ""))
        lowered = cause.lower()
        if any(token in lowered for token in ("rate limit", "too many requests", "timed out", "timeout", "temporarily unavailable", "connection reset")):
            return True
        return False

    def _coerce_status_code(self, status_code: object) -> int | None:
        if isinstance(status_code, int):
            return status_code
        if isinstance(status_code, str) and status_code.isdigit():
            return int(status_code)
        if isinstance(status_code, HTTPError):
            return status_code.code
        return None
