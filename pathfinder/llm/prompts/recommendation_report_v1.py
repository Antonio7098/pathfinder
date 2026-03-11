"""Recommendation report prompt implementation for template version v1."""

from __future__ import annotations

import json

from pathfinder.llm.prompts.base import VersionedPromptTemplate
from pathfinder.reporting.enums import RecommendationTemplateVersion


def render_recommendation_report_v1(context) -> tuple[str, str]:
    input_artifact = context.input_artifact
    context_bundle = context.context_bundle
    system_prompt = (
        "You are Pathfinder's recommendation report engine. "
        "You must stay file-first, grounded, and explainable. "
        "Do not invent files, edges, or mitigations unsupported by the supplied path and files. "
        "Prioritize concrete code-review and mitigation actions for the most important choke points. "
        "Every recommendation must cite only provided file paths, node ids, and edge ids. "
        "Return exactly one JSON object and nothing else. "
        "The first character of your response must be '{' and the last character must be '}'. "
        "Do not write markdown, headings, bullets, commentary, or code fences. "
        "Use this exact schema shape: "
        "{"
        "\"path_narrative\": string, "
        "\"target_rationale\": string, "
        "\"top_priority_file_path\": string, "
        "\"top_priority_rationale\": string, "
        "\"recommendations\": ["
        "{"
        "\"priority\": \"critical\"|\"high\"|\"medium\"|\"low\", "
        "\"title\": string, "
        "\"summary\": string, "
        "\"mitigation_steps\": [string], "
        "\"primary_file_path\": string, "
        "\"supporting_file_paths\": [string], "
        "\"supporting_node_ids\": [string], "
        "\"supporting_edge_ids\": [string], "
        "\"confidence\": number"
        "}"
        "]"
        "}. "
        "If unsure, still emit valid JSON that matches the schema."
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
    return system_prompt, json.dumps(payload, indent=2, sort_keys=True)


RECOMMENDATION_REPORT_V1_TEMPLATE = VersionedPromptTemplate(
    template_version=RecommendationTemplateVersion.V1.value,
    prompt_version="recommendation-report-prompt-v1",
    renderer=render_recommendation_report_v1,
)
