from security_evaluators.security_tools import PathfinderAI
from pprint import pprint

pathfinder = PathfinderAI(model="gpt-5.3-codex")
source_node = pathfinder.analyze_node("./tool_tester.py")
pprint(source_node)
target_node = pathfinder.analyze_node("./security_evaluators/security_tools.py")
pprint(target_node)
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

pprint(
    pathfinder.analyze_edge(
        structural_edge=structural_edge,
        source_node=source_node,
        target_node=target_node,
    )
)
