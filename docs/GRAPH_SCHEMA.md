# Graph Schema Proposal

For the concrete shipped structural artifact shape and extraction behavior, see:

* `docs/STRUCTURAL_GRAPH_EXTRACTION.md`

## Purpose

This document proposes the canonical graph schema for Pathfinder's MVP and notes the subset that is implemented today.

It is derived from:

* `docs/ARCHITECTURE.md`
* `docs/PRD.md`

The goal is to define a graph model that is:

* grounded in real files and real code relationships
* expressive enough for attack-transition reasoning
* simple enough for an MVP implementation
* compatible with deterministic path search after scoring

## Current implementation status

The repository currently implements the **structural subset** of this schema:

* `file` nodes
* `structural_edges`
* empty `attack_edges`
* `summary`
* `diagnostics`

Attack-edge materialization and LLM scoring remain later phases.

Separately, the repository now implements a **post-search recommendation reporting boundary** that is intentionally not folded into the graph schema:

* `RecommendationReportInputArtifact`
* `RecommendationReportArtifact`

Those artifacts consume selected paths and file context after search; they do not redefine graph nodes or edges.

---

## Recommended Graph Model

Pathfinder should use a **typed property graph** with:

* **file nodes** as the only node type in the MVP
* **structural edges** for code-derived relationships
* **attack edges** for attacker movement hypotheses derived from structure
* **node roles** expressed as flags on file nodes rather than separate node types

This preserves the architectural distinction:

* structural edges are **evidence**
* attack edges are **searchable attack transitions**
* file nodes can act as **entry**, **transition**, or **target** nodes depending on flags and path context

---

## Node Type: `file`

Each source file in the repository is represented as one node.

### Required fields

* `id`: stable unique identifier, e.g. normalized file path
* `path`: repository-relative file path
* `language`: primary language, e.g. `python`, `javascript`, `typescript`
* `node_type`: always `file` for MVP

### Recommended path-role fields

* `entrypoint_flag`: whether the file is externally reachable or likely attacker-reachable
* `target_flag`: whether the file is a plausible attacker destination or end node

`transition` is an implicit role rather than a separate node type. Any file that is not acting as the terminal target in a path can still serve as an intermediate transition node.

### Recommended structural fields

* `import_count`: number of outbound imports/includes/references
* `in_degree_structural`: inbound structural edge count
* `out_degree_structural`: outbound structural edge count
* `tags`: optional labels such as `auth`, `admin`, `db`, `api`, `storage`

The currently implemented structural artifact includes these structural count fields today.

### Recommended security scoring fields

* `normalized_risk_score`: normalized `0..1`, used as the attacker payoff or value of reaching this file as a target
* `confidence`: normalized `0..1`
* `rationale`: short explanation for why the file matters

### Recommended score container

For the MVP, the canonical per-file LLM outputs should be:

* `target_flag`
* `normalized_risk_score`
* `confidence`
* `rationale`

If the team wants richer decomposition, file scoring can also store optional sub-scores in a general score object:

* `security_scores`: object containing the file's attacker-relevance metrics

Goal-conditioned score maps can be added later once the baseline pathing works reliably. In the MVP, `normalized_risk_score` is the canonical node-level value used to rank target nodes.

### LLM file analysis pattern

For the MVP, Pathfinder should perform **one LLM call per file**.

That call should classify whether the file is a likely attacker target and assign the file's node-level attacker value.

---

## Edge Type: `structural`

Structural edges represent code relationships extracted from the repository.

### Required fields

* `id`: unique edge identifier
* `edge_type`: always `structural`
* `source`: source file node id
* `target`: target file node id
* `relationship_type`: type of code relationship

### Allowed `relationship_type` values for MVP

* `imports`
* `calls`
* `references`
* `includes`
* `shared_utility`

Currently emitted in implementation:

* `imports`
* `calls`
* `references`

`includes` and `shared_utility` remain allowed schema values for future extractor coverage.

### Recommended evidence fields

* `evidence`: short extracted proof, e.g. import symbol, call site, include target
* `extractor`: source of extraction, e.g. `codegraph`, `ast`, `indexer`
* `confidence`: normalized `0..1`

Current implementation also includes:

* `evidence_relations`: aggregated raw relation names used to build the edge
* `evidence_count`: number of preserved provenance items
* `provenance`: detailed structural evidence records

Structural edges should never be invented by the LLM.

---

## Edge Type: `attack_transition`

Attack edges represent plausible attacker movement between files.

These edges are derived from one or more structural edges and then scored.

### Required fields

* `id`: unique edge identifier
* `edge_type`: always `attack_transition`
* `source`: source file node id
* `target`: target file node id
* `attack_type`: attacker movement label
* `structural_basis_edge_ids`: list of structural edge ids supporting this edge
* `edge_attack_cost`: numeric traversal cost used by search

### Recommended attack fields

* `transition_likelihood`: normalized `0..1`
* `required_capability`: ordinal or enum such as `low`, `medium`, `high`
* `detection_risk`: normalized `0..1`
* `confidence`: normalized `0..1`
* `rationale`: short explanation for why the transition is plausible
* `excluded_flag`: boolean for filtered or disallowed edges

### Suggested `attack_type` values for MVP

* `sql_injection`
* `broken_authentication`
* `broken_authorization`
* `idor`
* `unsafe_deserialization`
* `command_injection`
* `session_abuse`
* `privilege_propagation`
* `unsafe_database_access`

### LLM attack-edge generation pattern

For the MVP, Pathfinder should perform **one LLM call per structural edge**.

That call should decide whether the structural relationship supports a plausible attacker move and, if so, emit an `attack_transition` edge with `attack_type`, `edge_attack_cost`, confidence, and rationale. If no plausible attacker move exists, no attack edge should be materialized for that structural edge.

---

## Canonical JSON Shape

The graph can be serialized as a document with separate node and edge collections.

```json
{
  "graph_id": "repo:pathfinder",
  "version": "mvp-v1",
  "repo_path": "/path/to/repo",
  "nodes": [],
  "structural_edges": [],
  "attack_edges": [],
  "summary": {},
  "diagnostics": {}
}
```

### Example file node

```json
{
  "id": "api/auth.js",
  "path": "api/auth.js",
  "language": "javascript",
  "node_type": "file",
  "entrypoint_flag": true,
  "target_flag": true,
  "tags": ["auth", "api"],
  "normalized_risk_score": 0.86,
  "confidence": 0.82,
  "security_scores": {
    "exploitability": 0.78,
    "privilege_gain": 0.91,
    "data_access_value": 0.44,
    "lateral_movement_value": 0.73,
    "detection_risk": 0.40,
    "confidence": 0.82,
    "normalized_risk_score": 0.86
  }
}
```

### Example structural edge

```json
{
  "id": "se:api/auth.js->api/admin.js:calls",
  "edge_type": "structural",
  "source": "api/auth.js",
  "target": "api/admin.js",
  "relationship_type": "calls",
  "evidence": "auth middleware invokes admin route guard",
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
      "source_logical_key": "symbol:api/auth.js::guard",
      "target_logical_key": "symbol:api/admin.js::admin_route",
      "source_symbol": "guard",
      "target_symbol": "admin_route"
    }
  ]
}
```

### Example summary and diagnostics

```json
{
  "summary": {
    "file_count": 79,
    "structural_edge_count": 264,
    "attack_edge_count": 0,
    "evidence_count": 710,
    "files_by_language": {"python": 79},
    "edges_by_relationship_type": {"calls": 86, "imports": 176, "references": 2}
  },
  "diagnostics": {
    "candidate_relation_count": 958,
    "emitted_edge_count": 264,
    "deduplicated_evidence_count": 0,
    "dropped_self_edges": 59,
    "dropped_missing_targets": 0,
    "omitted_relations": {"exports": 189}
  }
}
```

### Example attack edge

```json
{
  "id": "ae:api/auth.js->api/admin.js:broken_authorization",
  "edge_type": "attack_transition",
  "source": "api/auth.js",
  "target": "api/admin.js",
  "attack_type": "broken_authorization",
  "structural_basis_edge_ids": ["se:api/auth.js->api/admin.js:calls"],
  "transition_likelihood": 0.81,
  "required_capability": "medium",
  "detection_risk": 0.38,
  "confidence": 0.79,
  "edge_attack_cost": 0.42,
  "rationale": "authentication context can influence access to privileged route logic",
  "excluded_flag": false
}
```

---

## Graph Constraints

To keep the MVP reliable, enforce these rules:

1. Every scored file node must include `target_flag` and `normalized_risk_score`.
2. Every `attack_transition` edge must reference existing `file` nodes.
3. Every `attack_transition` edge must cite at least one supporting structural edge.
4. `normalized_risk_score`, `transition_likelihood`, `confidence`, and `detection_risk` must be normalized to `0..1`.
5. `edge_attack_cost` must be non-negative.
6. `id` and `path` for file nodes must be stable across runs for the same repository state.
7. Structural extraction is authoritative for graph connectivity; LLMs score and label but do not create unsupported structural relationships.
8. Attack edges may only be materialized from existing structural edges analyzed by the per-edge LLM pass.
9. `summary.file_count` must match serialized node count.
10. `summary.structural_edge_count` must match serialized structural edge count.
11. Structural edges must reference existing file node ids.

---

## Search Semantics

The search graph should use:

* **nodes** = file nodes with entry/transition/target roles and target payoff metadata
* **edges** = attack-transition edges with traversal cost

Recommended MVP path search:

* start from files with `entrypoint_flag = true`
* terminate at files with `target_flag = true`
* traverse using attack edges and their costs

Recommended decomposition:

`path_traversal_cost(P) = Σ(edge_attack_cost(e) + hop_penalty)`

`path_target_value(P) = normalized_risk_score(last_node(P))`

This matches the architecture guidance:

* lower edge cost means easier attacker movement
* higher target-node risk means more attractive attacker destination
* hop penalty discourages unrealistic long chains

`normalized_risk_score` belongs to the target node, not to the per-hop traversal function. Pathfinder can rank candidate paths using low traversal cost and high target value, but should not hide node risk inside edge traversal cost.

---

## Minimal MVP vs Later Extensions

### Minimal MVP

Architectural MVP target state:

* `file` nodes
* `structural` edges
* `attack_transition` edges
* `entrypoint_flag` and `target_flag` on file nodes
* one LLM call per file to assign `target_flag` and `normalized_risk_score`
* one LLM call per structural edge to derive attack edges and `edge_attack_cost`
* node risk for target files
* edge traversal costs and rationales

Currently shipped subset:

* `file` nodes
* `structural` edges
* empty `attack_edges`
* `summary`
* `diagnostics`
* provenance-rich structural evidence

### Later extensions

Future versions can add:

* goal-conditioned score maps
* grouped file clusters or service overlays
* vulnerability nodes such as CVEs or findings
* runtime entities such as APIs, databases, queues, or identities
* scenario/run records and stored path results
* analyst annotations and mitigation status

---

## Recommendation

For Pathfinder's MVP, the best schema is:

* **one file node per source file**
* **one structural edge per extracted code relationship**
* **file roles expressed as entry / transition / target flags rather than separate node types**
* **one per-file LLM pass to assign target flags and node risk**
* **one per-structural-edge LLM pass to materialize plausible attack transitions and edge traversal cost**

This gives the team a graph that is explainable, security-specific, and directly usable for weighted path search.