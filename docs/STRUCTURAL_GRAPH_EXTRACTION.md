# Structural Graph Extraction

## Purpose

This document describes the currently implemented structural graph extraction phase in Pathfinder.

It covers:

* what is implemented today
* how CodeGraph is used
* how Pathfinder projects file-to-file structural edges
* what the output artifact contains
* how to run it
* current limitations

This is the shipped **phase-1 foundation** of Pathfinder.

Related docs:

* `README.md`
* `docs/ARCHITECTURE.md`
* `docs/PRD.md`
* `docs/GRAPH_SCHEMA.md`

---

## What is implemented today

Pathfinder currently implements the **structural graph layer** only.

Implemented now:

* repository ingestion via CodeGraph / `ucp-content`
* projection into a file-level structural graph
* deterministic JSON artifact generation
* provenance-rich structural edges
* summary and diagnostics output
* a minimal graph viewer for structural artifacts

Not implemented yet:

* attack-edge derivation
* per-file LLM target/risk scoring
* deterministic path ranking over attack edges

---

## High-level flow

The implemented pipeline is:

1. build a CodeGraph from a repository
2. read the CodeGraph document blocks
3. identify file and symbol blocks
4. map symbol relationships back to owning files
5. emit file-to-file structural edges
6. persist a deterministic structural graph artifact

In code, the main pieces are:

* `pathfinder/adapters/codegraph.py`
* `pathfinder/adapters/codegraph_models.py`
* `pathfinder/structural/projector.py`
* `pathfinder/structural/models.py`
* `pathfinder/structural/service.py`

---

## Extraction backbone

Pathfinder does not parse repositories directly in this phase.

Instead, it uses CodeGraph as the extraction backbone and then applies a Pathfinder-owned projection layer on top.

That separation is intentional:

* CodeGraph handles repository indexing and code relationship extraction
* Pathfinder owns the file-level structural artifact and its invariants

This keeps Pathfinder grounded while avoiding tight coupling between the rest of the product and raw extractor details.

---

## Structural projection rules

The projector reads CodeGraph file and symbol blocks and collapses them into file-to-file structural edges.

### Current relation mappings

CodeGraph relations are mapped into Pathfinder structural relationships as follows:

* `imports` -> `imports`
* `imports_symbol` -> `imports`
* `reexports` -> `imports`
* `uses_symbol` -> `calls`
* `extends` -> `references`
* `implements` -> `references`

### Current behavior

The projector also:

* drops self-edges
* tracks omitted relations in diagnostics
* preserves per-edge provenance
* deduplicates repeated provenance evidence
* emits stable ordering for nodes and edges

### Intentionally omitted relations

Some extractor relations are currently **not** projected into structural edges.

Important examples:

* `exports`
* `for_type`

These are currently treated as ownership/provenance signals rather than high-value file-to-file structural dependencies.

---

## Output artifact

The structural extraction command writes a deterministic JSON artifact with these top-level fields:

* `graph_id`
* `version`
* `repo_path`
* `nodes`
* `structural_edges`
* `attack_edges`
* `summary`
* `diagnostics`

### Nodes

Nodes are files.

Current implemented fields include:

* `id`
* `path`
* `language`
* `node_type`
* `entrypoint_flag`
* `target_flag`
* `import_count`
* `in_degree_structural`
* `out_degree_structural`

Some fields exist now for later compatibility but are not yet meaningfully populated by an AI scoring phase.

### Structural edges

Structural edges are file-to-file relationships.

Current implemented fields include:

* `id`
* `edge_type`
* `source`
* `target`
* `relationship_type`
* `structural_basis`
* `evidence`
* `extractor`
* `confidence`
* `evidence_relations`
* `evidence_count`
* `provenance`

### Summary

The summary provides artifact-level counts such as:

* file count
* structural edge count
* attack edge count
* evidence count
* files by language
* edges by relationship type

### Diagnostics

Diagnostics provide operational visibility into projection behavior, including:

* candidate relation count
* emitted edge count
* deduplicated evidence count
* dropped self-edges
* dropped missing targets
* omitted relations

---

## Validation and invariants

The structural artifact is validated before it is accepted.

Current fail-fast checks include:

* duplicate file node ids are rejected
* structural edges must reference existing file nodes
* `summary.file_count` must match serialized node count
* `summary.structural_edge_count` must match serialized structural edge count

This is part of the project's "fail fast, fail loudly" rule.

---

## Default repository filtering

The extractor excludes common generated, cache, and environment directories by default.

Examples include:

* `.git`
* `target`
* `node_modules`
* `dist`
* `build`
* `__pycache__`
* `.venv`
* `venv`
* `.pytest_cache`
* `.mypy_cache`
* `.ruff_cache`
* `.tox`
* `.next`
* `.turbo`
* `coverage`

This keeps the structural graph focused on real source relationships rather than environment noise.

---

## Commands

### Build a structural graph

Run:

`python -m pathfinder.cli build-structural-graph --repo <repo> --output structural_graph.json`

Optional raw CodeGraph artifact output:

`python -m pathfinder.cli build-structural-graph --repo <repo> --output structural_graph.json --raw-codegraph-output raw_codegraph.json`

### View a structural graph

Run:

`python -m pathfinder.cli serve-graph-viewer --graph structural_graph.json`

Then open:

`http://127.0.0.1:8000`

---

## Testing and validation performed

The structural phase has been validated with:

* fixture-based tests for Python and TypeScript
* reexport handling tests
* generated-directory exclusion tests
* viewer tests
* real-repository smoke runs across multiple repositories

For the current phase, the structural extractor is considered stable across representative Python, TypeScript, Rust, and mixed repos.

---

## Current limitations

This document describes a **structural-only** implementation.

Current limits:

* no attack edges are materialized yet
* no `target_flag` scoring pass exists yet
* no LLM reasoning is used in the structural layer
* no attack-path ranking is performed yet

These are later phases by design.

---

## Recommended next step

The next phase should build on the structural artifact rather than reopening the extractor unless a real relation gap appears in practice.

That means future work should start from:

* file-level scoring
* attack-edge derivation from structural edges
* deterministic path ranking over attack edges