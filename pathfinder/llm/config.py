"""Configuration helpers for LLM-backed usage."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.errors import ConfigurationError


def _parse_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned = value.strip().strip('"').strip("'")
        values[key.strip()] = cleaned
    return values


class OpenRouterSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: float = 60.0
    app_name: str = "Pathfinder"

    @classmethod
    def from_env(
        cls,
        *,
        model_override: str | None = None,
        timeout_seconds: float = 60.0,
        env_path: Path | None = None,
    ) -> "OpenRouterSettings":
        resolved_env_path = env_path or Path(".env")
        env_values = {**_parse_env_file(resolved_env_path), **os.environ}
        api_key = env_values.get("OPENROUTER_API_KEY")
        model = model_override or env_values.get("OPENROUTER_MODEL_ID")
        if not api_key:
            raise ConfigurationError(
                "Missing OpenRouter API key",
                context={"env_key": "OPENROUTER_API_KEY", "env_path": str(resolved_env_path)},
            )
        if not model:
            raise ConfigurationError(
                "Missing OpenRouter model id",
                context={"env_key": "OPENROUTER_MODEL_ID", "env_path": str(resolved_env_path)},
            )
        return cls(
            api_key=api_key,
            model=model,
            base_url=env_values.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            timeout_seconds=timeout_seconds,
            app_name=env_values.get("OPENROUTER_APP_NAME", "Pathfinder"),
        )


class MiniMaxSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    base_url: str = "https://api.minimax.io/v1/text/chatcompletion_v2"
    timeout_seconds: float = 60.0
    app_name: str = "Pathfinder"

    @classmethod
    def from_env(
        cls,
        *,
        model_override: str | None = None,
        timeout_seconds: float = 60.0,
        env_path: Path | None = None,
    ) -> "MiniMaxSettings":
        resolved_env_path = env_path or Path(".env")
        env_values = {**_parse_env_file(resolved_env_path), **os.environ}
        api_key = env_values.get("MINIMAX_API_KEY")
        model = model_override or env_values.get("MINIMAX_MODEL_ID") or "MiniMax-M2.5"
        if not api_key:
            raise ConfigurationError(
                "Missing MiniMax API key",
                context={"env_key": "MINIMAX_API_KEY", "env_path": str(resolved_env_path)},
            )
        return cls(
            api_key=api_key,
            model=model,
            base_url=env_values.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1/text/chatcompletion_v2"),
            timeout_seconds=timeout_seconds,
            app_name=env_values.get("MINIMAX_APP_NAME", "Pathfinder"),
        )
