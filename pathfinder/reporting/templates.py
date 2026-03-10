"""Versioned prompt templates for recommendation reporting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from pathfinder.llm.models import StructuredPrompt
from pathfinder.reporting.context import ReportContextBundle
from pathfinder.reporting.enums import RecommendationTemplateVersion
from pathfinder.reporting.input_models import RecommendationReportInputArtifact
from pathfinder.reporting.models import LLMRecommendationReportPayload
from pathfinder.errors import ConfigurationError


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RecommendationPromptTemplate:
    template_version: RecommendationTemplateVersion
    prompt_version: str

    def render(
        self,
        input_artifact: RecommendationReportInputArtifact,
        context_bundle: ReportContextBundle,
    ) -> StructuredPrompt:
        system_prompt = (
            "You are Pathfinder's recommendation report engine. "
            "You must stay file-first, grounded, and explainable. "
            "Do not invent files, edges, or mitigations unsupported by the supplied path and files. "
            "Prioritize concrete code-review and mitigation actions for the most important choke points. "
            "Every recommendation must cite only provided file paths, node ids, and edge ids."
        )
        payload = {
            "repo_path": input_artifact.repo_path,
            "path_id": input_artifact.path_id,
            "path_nodes": [node.model_dump(mode="json") for node in input_artifact.path_nodes],
            "path_edges": [edge.model_dump(mode="json") for edge in input_artifact.path_edges],
            "known_file_paths": [node.path for node in input_artifact.path_nodes] + [item.path for item in input_artifact.focal_files],
            "context_summary": context_bundle.summary.model_dump(mode="json"),
            "files": [item.model_dump(mode="json") for item in context_bundle.files],
            "missing_file_paths": context_bundle.missing_file_paths,
            "dropped_file_paths": context_bundle.dropped_file_paths,
            "response_contract": {
                "path_narrative": "short explanation of attacker movement through the supplied path",
                "target_rationale": "why the destination matters",
                "top_priority_file_path": "must be one of known_file_paths",
                "top_priority_rationale": "why to mitigate that file first",
                "recommendations": "3-5 grounded mitigation recommendations with citations",
            },
        }
        user_prompt = json.dumps(payload, indent=2, sort_keys=True)
        return StructuredPrompt(
            template_version=self.template_version.value,
            prompt_version=self.prompt_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            system_prompt_sha256=_sha256(system_prompt),
            user_prompt_sha256=_sha256(user_prompt),
        )


class RecommendationTemplateRegistry:
    def __init__(self) -> None:
        self._templates = {
            RecommendationTemplateVersion.V1: RecommendationPromptTemplate(
                template_version=RecommendationTemplateVersion.V1,
                prompt_version="recommendation-report-prompt-v1",
            )
        }

    def resolve(self, template_version: RecommendationTemplateVersion) -> RecommendationPromptTemplate:
        template = self._templates.get(template_version)
        if template is None:
            raise ConfigurationError("Unsupported recommendation report template version", context={"template_version": template_version.value})
        return template

    @staticmethod
    def response_model() -> type[LLMRecommendationReportPayload]:
        return LLMRecommendationReportPayload