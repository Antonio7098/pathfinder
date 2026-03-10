from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from pathfinder.errors import ValidationError
from pathfinder.llm.config import OpenRouterSettings
from pathfinder.llm.models import LLMProvider, StructuredLLMRequest, StructuredPrompt
from pathfinder.llm.openai_client import OpenAIStructuredLLMClient
from pathfinder.observability.logging import get_logger


class DummyPayload(BaseModel):
    result: str


class FakeCompletionsAPI:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeOpenAIClient:
    def __init__(self, response) -> None:
        self.completions = FakeCompletionsAPI(response)
        self.beta = SimpleNamespace(chat=SimpleNamespace(completions=self.completions))


def build_request() -> StructuredLLMRequest:
    return StructuredLLMRequest(
        provider=LLMProvider.OPENROUTER,
        model="openrouter/test-model",
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
        metadata={"trace": "abc"},
    )


def test_openai_client_translates_request_and_extracts_usage() -> None:
    response = SimpleNamespace(
        id="req_123",
        model="openrouter/test-model",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(parsed=DummyPayload(result="ok"), refusal=None))],
    )
    fake_client = FakeOpenAIClient(response)
    client = OpenAIStructuredLLMClient(
        get_logger("llm-test"),
        OpenRouterSettings(api_key="test", model="openrouter/test-model"),
        client=fake_client,
    )

    result = client.generate(build_request(), response_model=DummyPayload)

    assert result.parsed_output.result == "ok"
    assert result.invocation.provider_request_id == "req_123"
    assert result.invocation.usage is not None
    assert result.invocation.usage.total_tokens == 15
    call = fake_client.completions.calls[0]
    assert call["model"] == "openrouter/test-model"
    assert call["response_format"] is DummyPayload
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1]["content"] == "user"
    assert call["extra_headers"] == {"X-Title": "Pathfinder"}
    assert call["timeout"] == 12.0


def test_openai_client_raises_when_no_parsed_payload_is_present() -> None:
    response = SimpleNamespace(
        id="req_456",
        model="openrouter/test-model",
        usage=None,
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(parsed=None, refusal="refused"))],
    )
    client = OpenAIStructuredLLMClient(
        get_logger("llm-test"),
        OpenRouterSettings(api_key="test", model="openrouter/test-model"),
        client=FakeOpenAIClient(response),
    )

    with pytest.raises(ValidationError):
        client.generate(build_request(), response_model=DummyPayload)