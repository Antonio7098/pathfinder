"""Security evaluation prompt implementation for template version v1."""

from __future__ import annotations

import json

from pathfinder.llm.prompts.base import VersionedPromptTemplate


def render_file_security_evaluation_v1(context) -> tuple[str, str]:
    system_prompt = (
        "You are Pathfinder's file security evaluation engine. "
        "Stay grounded in the supplied file only. "
        "Return exactly one JSON object and no other text. "
        "Do not use markdown fences, prose, or commentary. "
        "Do not leave the response empty. "
        "All numeric scores must be floats between 0.0 and 1.0 inclusive. "
        "Keep rationale short and evidence-oriented."
    )
    payload = {
        "file_path": context.file_path,
        "code": context.code,
        "response_contract": {
            "tags": "short optional labels relevant to the file",
            "confidence": "float 0.0-1.0 for confidence in the assessment",
            "rationale": "short grounded rationale",
            "security_scores": {
                "exploitability": "float 0.0-1.0",
                "privilege_gain": "float 0.0-1.0",
                "data_access_value": "float 0.0-1.0",
                "lateral_movement_value": "float 0.0-1.0",
                "detection_risk": "float 0.0-1.0",
                "confidence": "float 0.0-1.0",
            },
        },
    }
    return system_prompt, json.dumps(payload, indent=2, sort_keys=True)


def render_edge_security_evaluation_v1(context) -> tuple[str, str]:
    system_prompt = (
        "You are Pathfinder's attack-transition derivation engine. "
        "You may only derive plausible attack transitions from the supplied structural edge. "
        "Return exactly one JSON object and no other text. "
        "Do not use markdown fences, prose, or commentary. "
        "Do not leave the response empty. "
        "If no grounded attack transition is justified, return {\"attacks\": []}. "
        "Only use attack_type values from the supplied enum. "
        "All probabilities and confidence values must be floats between 0.0 and 1.0 inclusive. "
        "Keep rationales short and evidence-oriented."
    )
    payload = {
        "structural_edge_id": context.structural_edge_id,
        "relationship_type": context.relationship_type,
        "source_file": {"path": context.source_path, "code": context.source_code},
        "target_file": {"path": context.target_path, "code": context.target_code},
        "valid_attack_types": list(context.valid_attack_types),
        "response_contract": {
            "attacks": [
                {
                    "attack_type": "must be one of valid_attack_types",
                    "transition_likelihood": "float 0.0-1.0",
                    "required_capability": "one of low, med, high",
                    "detection_risk": "float 0.0-1.0",
                    "edge_attack_cost": "non-negative float",
                    "confidence": "float 0.0-1.0",
                    "rationale": "short grounded rationale",
                }
            ]
        },
    }
    return system_prompt, json.dumps(payload, indent=2, sort_keys=True)


FILE_SECURITY_EVALUATION_V1_TEMPLATE = VersionedPromptTemplate(
    template_version="security-evaluation-v1",
    prompt_version="file-security-evaluation-prompt-v2",
    renderer=render_file_security_evaluation_v1,
)

EDGE_SECURITY_EVALUATION_V1_TEMPLATE = VersionedPromptTemplate(
    template_version="security-evaluation-v1",
    prompt_version="edge-security-evaluation-prompt-v2",
    renderer=render_edge_security_evaluation_v1,
)
