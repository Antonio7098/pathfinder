"""Service grouping prompt implementation for template version v1."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import PurePosixPath

from pathfinder.llm.prompts.base import VersionedPromptTemplate
from pathfinder.services.enums import ServiceTemplateVersion


def render_service_grouping_v1(context) -> tuple[str, str]:
    structural_graph = context.structural_graph
    graphcode_evidence = context.graphcode_evidence
    system_prompt = (
        "You are Pathfinder's service grouping engine. "
        "The canonical structural graph remains file-first; you are proposing a derived service overlay only. "
        "Do not invent file paths, edges, or services unsupported by the supplied structural graph. "
        "Group files into a grounded set of meaningful services and assign each service a layer label. "
        "Use the supplied graphcode evidence such as exported symbols, symbol interaction pairs, directory representative files, and grounded role hints when it helps identify real service boundaries. "
        "Prefer high coverage: minimize unclassified files when a coherent service, support subsystem, adapter layer, or test/fixture cluster is clearly grounded by the directory structure, symbol evidence, and structural edges. "
        "If the repository has a dominant package root such as src/, app/, pkg/, or a named project package, strongly prefer treating its immediate child directories as candidate services before collapsing them into a generic cluster. "
        "When a candidate service name clearly matches a directory bucket, such as dashboard, llm, reporting, structural, services, security_evaluators, adapters, or observability, include the grounded files from that matching bucket instead of leaving them for fallback clustering. "
        "If you use repository vocabulary in CamelCase names like ReportingService or StructuralGraphService, you must still ground them with the exact file paths from the matching directory bucket. "
        "Choose concise, specific service names that stay close to the repository's own subsystem language; prefer directory or exported-symbol vocabulary over generic names like core, misc, or service layer when better grounded names exist. "
        "If you see a clear bootstrap, API surface, migration, test, prompt, adapter, or graph-pipeline cluster in the role hints, you may use that evidence to create a small grounded service instead of leaving the files for deterministic fallback. "
        "Keep the response compact: architecture_summary should be at most two short sentences, and each service summary and rationale should be at most one short sentence. "
        "If a file is shared across multiple services, put it in shared_file_paths instead of inventing duplicate service boundaries."
    )
    payload = {
        "repo_path": structural_graph.repo_path,
        "graph_id": structural_graph.graph_id,
        "summary": structural_graph.summary.model_dump(mode="json"),
        "directory_summary": _directory_summary(structural_graph),
        "directory_relationship_summary": _directory_relationship_summary(structural_graph),
        "graphcode_context": graphcode_evidence.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
        "files": [
            {
                "path": node.path,
                "language": node.language,
                "import_count": node.import_count,
                "in_degree_structural": node.in_degree_structural,
                "out_degree_structural": node.out_degree_structural,
                "tags": node.tags,
            }
            for node in structural_graph.nodes
        ],
        "structural_edges": [
            {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "relationship_type": edge.relationship_type.value,
                "evidence_count": edge.evidence_count,
            }
            for edge in structural_graph.structural_edges
        ],
        "response_contract": {
            "architecture_summary": "at most two short sentences summarizing the inferred architecture",
            "services": "a compact set of grounded services, each with a layer and only known file paths",
            "shared_file_paths": "known file paths that are clearly cross-cutting or claimed by multiple services",
            "unclassified_file_paths": "known file paths that truly do not fit any grounded service confidently after considering support/tooling/test clusters",
            "layer_enum": ["edge", "application", "domain", "data", "shared", "unknown"],
        },
    }
    return system_prompt, json.dumps(payload, indent=2, sort_keys=True)


def _directory_summary(structural_graph) -> list[dict[str, object]]:
    buckets: dict[str, list[str]] = {}
    for node in structural_graph.nodes:
        key = _directory_bucket(node.path)
        buckets.setdefault(key, []).append(node.path)
    summary: list[dict[str, object]] = []
    for key in sorted(buckets):
        paths = sorted(buckets[key])
        summary.append({"directory": key, "file_count": len(paths), "sample_paths": paths[:8]})
    return summary


def _directory_relationship_summary(structural_graph) -> list[dict[str, object]]:
    counts: Counter[tuple[str, str]] = Counter()
    for edge in structural_graph.structural_edges:
        counts[(_directory_bucket(edge.source), _directory_bucket(edge.target))] += 1
    summary: list[dict[str, object]] = []
    for (source_directory, target_directory), edge_count in sorted(counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))[:50]:
        summary.append({"source_directory": source_directory, "target_directory": target_directory, "edge_count": edge_count})
    return summary


def _directory_bucket(path: str) -> str:
    parts = PurePosixPath(path).parts
    if len(parts) >= 3:
        return "/".join(parts[:2])
    if len(parts) >= 2:
        return parts[0]
    return "."


SERVICE_GROUPING_V1_TEMPLATE = VersionedPromptTemplate(
    template_version=ServiceTemplateVersion.V1.value,
    prompt_version="service-grouping-prompt-v5",
    renderer=render_service_grouping_v1,
)
