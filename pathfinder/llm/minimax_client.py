"""MiniMax HTTP adapter for structured JSON responses."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, TypeVar
from urllib.error import HTTPError
from urllib import request as urllib_request

from pathfinder.errors import ExternalDependencyError, ValidationError
from pathfinder.llm.config import MiniMaxSettings
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider, StructuredLLMRequest, StructuredLLMResult, TokenUsage
from pathfinder.observability.logging import log_event


StructuredOutputT = TypeVar("StructuredOutputT")


class MiniMaxStructuredLLMClient:
    def __init__(self, logger, config: MiniMaxSettings, *, opener: Any | None = None) -> None:
        self._logger = logger
        self._config = config
        self._opener = opener or urllib_request.urlopen
        self._max_parse_attempts = 3

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

        body = json.dumps(
            {
                "model": request.model,
                "messages": [
                    {"role": "system", "name": self._config.app_name, "content": request.prompt.system_prompt},
                    {"role": "user", "name": "User", "content": request.prompt.user_prompt},
                ],
                "temperature": request.temperature,
                "max_completion_tokens": request.max_output_tokens,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        http_request = urllib_request.Request(
            self._config.base_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        started = perf_counter()
        last_validation_error: ValidationError | None = None
        response_json: dict[str, Any] | None = None
        for attempt in range(1, self._max_parse_attempts + 1):
            response_json = self._perform_http_request(http_request, request=request)
            try:
                parsed = self._extract_parsed_output(response_json, response_model=response_model)
                break
            except ValidationError as exc:
                last_validation_error = exc
                if attempt == self._max_parse_attempts:
                    raise
                log_event(
                    self._logger,
                    "llm.request.retrying",
                    fields={
                        "provider": request.provider.value,
                        "base_url": self._config.base_url,
                        "model": request.model,
                        "operation_name": request.operation_name,
                        "attempt": attempt,
                        "max_attempts": self._max_parse_attempts,
                        "cause": str(exc),
                    },
                )
        else:
            if last_validation_error is not None:
                raise last_validation_error
            raise ValidationError("Structured LLM request failed without a parsed payload")

        assert response_json is not None
        duration = perf_counter() - started
        usage = self._extract_usage(response_json)
        finish_reason = self._extract_finish_reason(response_json)
        provider_request_id = response_json.get("id")

        invocation = LLMInvocationRecord(
            provider=LLMProvider.MINIMAX,
            base_url=self._config.base_url,
            model=response_json.get("model", request.model),
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

    def _perform_http_request(self, http_request: urllib_request.Request, *, request: StructuredLLMRequest) -> dict[str, Any]:
        try:
            with self._opener(http_request, timeout=request.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
                response_json = json.loads(response_body)
                status_code = getattr(response, "status", None) or response.getcode()
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            try:
                response_json = json.loads(response_body) if response_body else {}
            except json.JSONDecodeError:
                response_json = {"raw_response": response_body[:500]}
            raise ExternalDependencyError(
                "Structured LLM request failed",
                context={
                    "provider": request.provider.value,
                    "base_url": self._config.base_url,
                    "model": request.model,
                    "operation_name": request.operation_name,
                    "status_code": exc.code,
                    "response": response_json,
                    "cause": str(exc),
                },
            ) from exc
        except Exception as exc:
            raise ExternalDependencyError(
                "Structured LLM request failed",
                context={
                    "provider": request.provider.value,
                    "base_url": self._config.base_url,
                    "model": request.model,
                    "operation_name": request.operation_name,
                    "status_code": None,
                    "cause": str(exc),
                },
            ) from exc

        if status_code and status_code >= 400:
            raise ExternalDependencyError(
                "Structured LLM request failed",
                context={
                    "provider": request.provider.value,
                    "base_url": self._config.base_url,
                    "model": request.model,
                    "operation_name": request.operation_name,
                    "status_code": status_code,
                    "response": response_json,
                },
            )
        return response_json

    def _extract_parsed_output(self, response_json: dict[str, Any], *, response_model: type[StructuredOutputT]) -> StructuredOutputT:
        choices = response_json.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content")
        if not content:
            raise ValidationError(
                "Structured LLM response did not contain content",
                context={"provider_request_id": response_json.get("id")},
            )
        try:
            payload = json.loads(self._coerce_json_content(content))
            payload = self._repair_payload(payload, response_model_name=response_model.__name__)
            return response_model.model_validate(payload)
        except Exception as exc:
            raise ValidationError(
                "Structured LLM response could not be parsed into the expected schema",
                context={"provider_request_id": response_json.get("id"), "cause": str(exc), "content": content[:500]},
            ) from exc

    def _coerce_json_content(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        return stripped

    def _repair_payload(self, payload: Any, *, response_model_name: str) -> Any:
        if not isinstance(payload, dict):
            return payload
        if response_model_name == "LLMServiceGroupingPayload":
            return self._repair_service_grouping_payload(payload)
        if response_model_name == "FileSecurityAnalysisPayload":
            return self._repair_file_security_payload(payload)
        if response_model_name == "LLMRecommendationReportPayload":
            return self._repair_recommendation_report_payload(payload)
        return payload

    def _repair_service_grouping_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        services = payload.get("services")
        if not isinstance(services, list):
            return payload
        repaired_services: list[Any] = []
        for item in services:
            if not isinstance(item, dict):
                repaired_services.append(item)
                continue
            repaired = dict(item)
            if not repaired.get("summary"):
                repaired["summary"] = repaired.get("rationale") or f"Service inferred for {repaired.get('name', 'unknown')}"
            repaired_services.append(repaired)
        result = dict(payload)
        result["services"] = repaired_services
        return result

    def _repair_file_security_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "security_scores" in payload:
            return payload
        score = self._coerce_float(
            payload.get("confidence"),
            default=0.0,
        )
        sensitivity = str(payload.get("sensitivity", "")).strip().lower()
        level_map = {
            "low": 0.2,
            "medium": 0.5,
            "med": 0.5,
            "high": 0.8,
            "critical": 1.0,
        }
        base = level_map.get(sensitivity, score)
        result = dict(payload)
        result["security_scores"] = {
            "exploitability": base,
            "privilege_gain": base,
            "data_access_value": base,
            "lateral_movement_value": base,
            "detection_risk": max(0.0, min(1.0, 1.0 - (base / 2))),
            "confidence": score,
        }
        if "confidence" not in result:
            result["confidence"] = score
        if "rationale" not in result:
            result["rationale"] = "Provider returned a partial security analysis that was normalized into the expected schema."
        if "tags" not in result or not isinstance(result.get("tags"), list):
            result["tags"] = []
        return result

    def _repair_recommendation_report_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(payload)
        recommendations = result.get("recommendations")
        if isinstance(recommendations, list):
            repaired_recommendations = [
                self._repair_recommendation_item(item, payload=result)
                for item in recommendations
            ]
            result["recommendations"] = repaired_recommendations
        return result

    def _repair_recommendation_item(self, item: Any, *, payload: dict[str, Any]) -> Any:
        if not isinstance(item, dict):
            return item
        repaired = dict(item)
        title = (
            repaired.get("title")
            or repaired.get("recommendation")
            or repaired.get("action")
            or "Grounded mitigation recommendation"
        )
        summary = (
            repaired.get("summary")
            or repaired.get("rationale")
            or repaired.get("why")
            or repaired.get("details")
            or title
        )
        mitigation_steps = repaired.get("mitigation_steps")
        if not isinstance(mitigation_steps, list):
            mitigation_steps = self._coerce_string_list(
                repaired.get("steps")
                or repaired.get("implementation_steps")
                or repaired.get("actions")
                or repaired.get("mitigation")
                or repaired.get("recommendation")
            )
        primary_file_path = (
            repaired.get("primary_file_path")
            or repaired.get("file_path")
            or repaired.get("file")
            or repaired.get("path")
            or payload.get("top_priority_file_path")
        )
        supporting_file_paths = self._coerce_string_list(
            repaired.get("supporting_file_paths")
            or repaired.get("files")
            or repaired.get("evidence_file_paths")
        )
        supporting_node_ids = self._coerce_string_list(
            repaired.get("supporting_node_ids")
            or repaired.get("node_ids")
        )
        supporting_edge_ids = self._coerce_string_list(
            repaired.get("supporting_edge_ids")
            or repaired.get("edge_ids")
        )
        confidence = self._coerce_float(repaired.get("confidence"), default=0.5)
        priority = str(repaired.get("priority") or "").strip().lower()
        if priority not in {"critical", "high", "medium", "low"}:
            priority = self._priority_from_index_text(title=title, summary=summary)
        return {
            "priority": priority,
            "title": title,
            "summary": summary,
            "mitigation_steps": mitigation_steps or [title],
            "primary_file_path": primary_file_path,
            "supporting_file_paths": supporting_file_paths,
            "supporting_node_ids": supporting_node_ids,
            "supporting_edge_ids": supporting_edge_ids,
            "confidence": confidence,
        }

    def _priority_from_index_text(self, *, title: str, summary: str) -> str:
        text = f"{title} {summary}".lower()
        if "critical" in text:
            return "critical"
        if "high" in text:
            return "high"
        return "medium"

    def _coerce_string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if "\n" in text:
                return [line.strip("-* 0123456789. \t") for line in text.splitlines() if line.strip()]
            return [text]
        return []

    def _coerce_float(self, value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _extract_finish_reason(self, response_json: dict[str, Any]) -> str | None:
        choices = response_json.get("choices") or []
        if not choices:
            return None
        return choices[0].get("finish_reason")

    def _extract_usage(self, response_json: dict[str, Any]) -> TokenUsage | None:
        usage = response_json.get("usage")
        if usage is None:
            return None
        return TokenUsage(
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )
