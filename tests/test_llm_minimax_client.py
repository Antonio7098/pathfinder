from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest
from pydantic import BaseModel

from pathfinder.errors import ValidationError
from pathfinder.llm.config import MiniMaxSettings
from pathfinder.llm.minimax_client import MiniMaxStructuredLLMClient
from pathfinder.llm.models import LLMProvider, StructuredLLMRequest, StructuredPrompt
from pathfinder.observability.logging import get_logger
from pathfinder.reporting.models import LLMRecommendationReportPayload
from pathfinder.security_evaluators.models import FileSecurityAnalysisPayload


class DummyPayload(BaseModel):
    result: str


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object], *, status: int = 200) -> None:
        self.status = status
        self._buffer = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._buffer.read()

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def build_request() -> StructuredLLMRequest:
    return StructuredLLMRequest(
        provider=LLMProvider.MINIMAX,
        model="MiniMax-M2.5",
        operation_name="test.operation",
        response_format_name="DummyPayload",
        prompt=StructuredPrompt(
            template_version="template-v1",
            prompt_version="prompt-v1",
            system_prompt="system",
            user_prompt="user",
            system_prompt_sha256="syshash",
            user_prompt_sha256="userhash",
        ),
        timeout_seconds=12.0,
        max_output_tokens=300,
    )


def test_minimax_client_parses_json_content_and_usage() -> None:
    seen: dict[str, object] = {}

    def fake_opener(req, timeout=0):
        seen["url"] = req.full_url
        seen["timeout"] = timeout
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return FakeHTTPResponse(
            {
                "id": "req_123",
                "model": "MiniMax-M2.5",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "{\"result\": \"ok\"}"},
                    }
                ],
            }
        )

    client = MiniMaxStructuredLLMClient(
        get_logger("llm-test"),
        MiniMaxSettings(api_key="test", model="MiniMax-M2.5"),
        opener=fake_opener,
    )

    result = client.generate(build_request(), response_model=DummyPayload)

    assert result.parsed_output.result == "ok"
    assert result.invocation.provider == LLMProvider.MINIMAX
    assert result.invocation.provider_request_id == "req_123"
    assert result.invocation.usage is not None
    assert result.invocation.usage.total_tokens == 15
    assert seen["url"] == "https://api.minimax.io/v1/text/chatcompletion_v2"
    assert seen["timeout"] == 12.0
    assert seen["body"]["model"] == "MiniMax-M2.5"
    assert seen["body"]["response_format"] == {"type": "json_object"}


def test_minimax_client_raises_on_invalid_content() -> None:
    def fake_opener(req, timeout=0):
        return FakeHTTPResponse(
            {
                "id": "req_456",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "{\"not_result\": \"nope\"}"},
                    }
                ],
            }
        )

    client = MiniMaxStructuredLLMClient(
        get_logger("llm-test"),
        MiniMaxSettings(api_key="test", model="MiniMax-M2.5"),
        opener=fake_opener,
    )

    with pytest.raises(ValidationError):
        client.generate(build_request(), response_model=DummyPayload)


def test_minimax_client_retries_transient_empty_content() -> None:
    responses = iter(
        [
            FakeHTTPResponse(
                {
                    "id": "req_empty",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": ""},
                        }
                    ],
                }
            ),
            FakeHTTPResponse(
                {
                    "id": "req_ok",
                    "model": "MiniMax-M2.5",
                    "usage": {"prompt_tokens": 11, "completion_tokens": 6, "total_tokens": 17},
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": "{\"result\": \"ok\"}"},
                        }
                    ],
                }
            ),
        ]
    )

    def fake_opener(req, timeout=0):
        return next(responses)

    client = MiniMaxStructuredLLMClient(
        get_logger("llm-test"),
        MiniMaxSettings(api_key="test", model="MiniMax-M2.5"),
        opener=fake_opener,
    )

    result = client.generate(build_request(), response_model=DummyPayload)

    assert result.parsed_output.result == "ok"
    assert result.invocation.provider_request_id == "req_ok"


def test_minimax_client_repairs_partial_file_security_payload() -> None:
    def fake_opener(req, timeout=0):
        return FakeHTTPResponse(
            {
                "id": "req_security",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "sensitivity": "HIGH",
                                    "confidence": 0.95,
                                    "rationale": "Security-sensitive module.",
                                    "tags": ["security-tool"],
                                }
                            )
                        },
                    }
                ],
            }
        )

    client = MiniMaxStructuredLLMClient(
        get_logger("llm-test"),
        MiniMaxSettings(api_key="test", model="MiniMax-M2.5"),
        opener=fake_opener,
    )

    result = client.generate(build_request(), response_model=FileSecurityAnalysisPayload)

    assert result.parsed_output.confidence == 0.95
    assert result.parsed_output.security_scores.exploitability == 0.8
    assert result.parsed_output.tags == ["security-tool"]


def test_minimax_client_repairs_alternate_recommendation_schema() -> None:
    def fake_opener(req, timeout=0):
        return FakeHTTPResponse(
            {
                "id": "req_report",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "path_narrative": "Narrative",
                                    "target_rationale": "Target rationale",
                                    "top_priority_file_path": "pkg/db.py",
                                    "top_priority_rationale": "Important target",
                                    "recommendations": [
                                        {
                                            "recommendation": "Sanitize error context",
                                            "file": "pkg/db.py",
                                            "steps": ["Mask secrets", "Avoid leaking paths"],
                                            "confidence": 0.8,
                                        }
                                    ],
                                }
                            )
                        },
                    }
                ],
            }
        )

    client = MiniMaxStructuredLLMClient(
        get_logger("llm-test"),
        MiniMaxSettings(api_key="test", model="MiniMax-M2.5"),
        opener=fake_opener,
    )

    result = client.generate(build_request(), response_model=LLMRecommendationReportPayload)

    assert result.parsed_output.recommendations[0].title == "Sanitize error context"
    assert result.parsed_output.recommendations[0].primary_file_path == "pkg/db.py"
    assert result.parsed_output.recommendations[0].mitigation_steps == ["Mask secrets", "Avoid leaking paths"]


def test_minimax_client_surfaces_http_status_code() -> None:
    def fake_opener(req, timeout=0):
        raise HTTPError(req.full_url, 429, "Too Many Requests", hdrs=None, fp=io.BytesIO(b'{"error":"rate limited"}'))

    client = MiniMaxStructuredLLMClient(
        get_logger("llm-test"),
        MiniMaxSettings(api_key="test", model="MiniMax-M2.5"),
        opener=fake_opener,
    )

    with pytest.raises(Exception) as exc_info:
        client.generate(build_request(), response_model=DummyPayload)

    assert getattr(exc_info.value, "context", {}).get("status_code") == 429
