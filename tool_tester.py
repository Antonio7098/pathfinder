from security_evaluators.security_tools import PathfinderAI
from pprint import pprint

pathfinder = PathfinderAI(model="gpt-5.3-codex")
# source_node = pathfinder.analyze_node("./tool_tester.py")
# pprint(source_node)
source_node = {
    "confidence": 0.9,
    "id": "./tool_tester.py",
    "node_type": "file",
    "normalized_risk_score": 0.108,
    "path": "./tool_tester.py",
    "rationale": "This script is a lightweight local tester that instantiates a "
    "security-analysis helper, analyzes a local file path, and "
    "prints results. It does not process untrusted external input, "
    "perform authentication/authorization actions, execute shell "
    "commands, or directly access sensitive resources. The main "
    "security uncertainty is delegated behavior inside the imported "
    "PathfinderAI implementation (not shown), which could involve "
    "network/model calls. Based on visible code only, risk is low.",
    "security_scores": {
        "confidence": 0.9,
        "data_access_value": 0.2,
        "detection_risk": 0.81,
        "exploitability": 0.14,
        "lateral_movement_value": 0.02,
        "normalized_risk_score": 0.108,
        "privilege_gain": 0.03,
    },
    "tags": ["tooling", "test-script", "local-file-analysis", "low-risk-orchestrator"],
}


# target_node = pathfinder.analyze_node("./security_evaluators/security_tools.py")
# pprint(target_node)
target_node = {
    "confidence": 0.86,
    "id": "./security_evaluators/security_tools.py",
    "node_type": "file",
    "normalized_risk_score": 0.444,
    "path": "./security_evaluators/security_tools.py",
    "rationale": "This module is an orchestration tool, not a direct exploit "
    "surface by itself, but it introduces meaningful security risk "
    "if upstream inputs are untrusted. It reads local files based on "
    "provided paths and sends full source code to a third-party LLM "
    "endpoint (OpenRouter), creating a clear data exposure pathway. "
    "Path handling uses os.path.join(repo_root, rel_path) without "
    "normalization/sandbox enforcement, so '../' style traversal "
    "could allow reading files outside the repository if file_paths "
    "is attacker-controlled. The analyze_edge method currently "
    "prints model output and calls exit(), which is a debug artifact "
    "that can cause denial-of-service behavior and operational "
    "instability. There is no schema validation/hardening of model "
    "responses beyond JSON parsing, but this is more robustness than "
    "direct privilege escalation. Overall: moderate exploitability "
    "in untrusted-input contexts, low direct privilege gain, high "
    "potential data value from exposed source/config files.",
    "security_scores": {
        "confidence": 0.86,
        "data_access_value": 0.82,
        "detection_risk": 0.58,
        "exploitability": 0.64,
        "lateral_movement_value": 0.33,
        "normalized_risk_score": 0.444,
        "privilege_gain": 0.21,
    },
    "tags": [
        "llm-integration",
        "external-api",
        "file-io",
        "path-traversal-risk",
        "data-exfiltration-risk",
        "debug-artifacts",
    ],
}


structural_edge = {
    "id": "se:./tool_tester.py->./security_evaluators/security_tools.py:calls",
    "edge_type": "structural",
    "source": "./tool_tester.py",
    "target": "./security_evaluators/security_tools.py",
    "relationship_type": "calls",
    "evidence": "tool tester invokes PathfinderAI",
    "extractor": "codegraph",
    "confidence": 1.0,
    "evidence_relations": ["uses_symbol"],
    "evidence_count": 1,
    "provenance": [
        {
            "raw_relation": "uses_symbol",
            "extractor": "codegraph",
            "source_block_id": "blk_source",
            "target_block_id": "blk_target",
            "source_logical_key": "symbol:./tool_tester.py::guard",
            "target_logical_key": "./security_evaluators/security_tools.py::admin_route",
            "source_symbol": "guard",
            "target_symbol": "admin_route",
        }
    ],
}


attacks = pathfinder.analyze_edge(
    structural_edge=structural_edge,
    source_node=source_node,
    target_node=target_node,
)

print("-" * 50)
print("Attacks:")
print("-" * 50)

print(attacks)
