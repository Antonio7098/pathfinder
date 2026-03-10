"""Reusable prompt-building helpers and versioned prompt registries."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar

from pathfinder.errors import ConfigurationError
from pathfinder.llm.models import StructuredPrompt


RenderContextT = TypeVar("RenderContextT")
VersionT = TypeVar("VersionT")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _version_label(value: object) -> str:
    raw_value = getattr(value, "value", value)
    return str(raw_value)


def build_structured_prompt(*, template_version: str, prompt_version: str, system_prompt: str, user_prompt: str) -> StructuredPrompt:
    return StructuredPrompt(
        template_version=template_version,
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        system_prompt_sha256=_sha256(system_prompt),
        user_prompt_sha256=_sha256(user_prompt),
    )


@dataclass(frozen=True, slots=True)
class VersionedPromptTemplate(Generic[RenderContextT]):
    template_version: str
    prompt_version: str
    renderer: Callable[[RenderContextT], tuple[str, str]]

    def render(self, context: RenderContextT) -> StructuredPrompt:
        system_prompt, user_prompt = self.renderer(context)
        return build_structured_prompt(
            template_version=self.template_version,
            prompt_version=self.prompt_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


class VersionedPromptRegistry(Generic[VersionT, RenderContextT]):
    def __init__(self, *, registry_name: str, templates: Mapping[VersionT, VersionedPromptTemplate[RenderContextT]]) -> None:
        self._registry_name = registry_name
        self._templates = dict(templates)

    def resolve(self, template_version: VersionT) -> VersionedPromptTemplate[RenderContextT]:
        template = self._templates.get(template_version)
        if template is None:
            raise ConfigurationError(
                "Unsupported prompt template version",
                context={"registry_name": self._registry_name, "template_version": _version_label(template_version)},
            )
        return template