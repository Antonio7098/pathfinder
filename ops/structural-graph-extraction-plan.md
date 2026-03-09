# Structural Graph Extraction Plan

## Status

- Branch: `feat/structural-graph-extraction`
- Pathfinder docs are aligned on the MVP shape:
  - files are the unit of reasoning
  - first build a structural file graph
  - only after that derive attack-transition edges
  - keep structural evidence separate from attack semantics

## Recommendation

Implement structural extraction as a **Pathfinder-owned projection layer on top of CodeGraph**, not by changing CodeGraph first.

That means:

1. use CodeGraph to ingest a repository
2. project its repo/file/symbol graph into a file-to-file structural graph
3. persist that structural graph as Pathfinder's canonical phase-1 artifact

## Principles that govern this plan

This plan must follow `AGENTS.md`.

Non-negotiable principles for this work:

- **file-first MVP**: keep files as the canonical node type
- **structural-graph-first**: structure is authoritative before any attack semantics
- **small modular files**: keep modules narrow and easy to inspect
- **Pydantic schemas + strong typing**: use explicit models and typed interfaces throughout
- **fail fast, fail loudly**: surface broken invariants immediately
- **observability is truth**: logs, summaries, and artifacts must reconcile
- **full explainability**: every structural edge must preserve provenance
- **deterministic artifacts**: stable ordering, stable ids, stable summaries

## Phase 1 — Bootstrap Pathfinder as a Python project

Pathfinder currently has docs only, so first create a minimal codebase shape.

Create:

- a Python package for Pathfinder
- a small CLI entrypoint for structural extraction
- tests and fixtures from day one

Suggested module layout:

- `pathfinder/adapters/codegraph.py`
- `pathfinder/structural/models.py`
- `pathfinder/structural/projector.py`
- `pathfinder/structural/io.py`
- `pathfinder/observability/logging.py`
- `pathfinder/errors.py`
- `pathfinder/cli.py`
- `tests/fixtures/...`
- `tests/test_structural_graph.py`

Design constraints:

- keep files small and modular
- separate models, adapters, orchestration, persistence, and CLI concerns
- prefer explicit data flow over hidden global state

## Phase 2 — Build the CodeGraph adapter

This layer should do only a few things:

- build a CodeGraph from a repo path
- save and load raw CodeGraph artifacts
- normalize build config
- expose a clean typed interface to the projector

Purpose:

- isolate `ucp` / CodeGraph details
- keep the rest of Pathfinder independent from binding specifics
- make replacement or mocking easy in tests

Expected outputs from this layer:

- typed repository extraction result
- typed raw graph artifact metadata
- extraction diagnostics and counts

## Phase 3 — Define the structural graph schema

Before coding the projector, define Pathfinder's own file-graph model.

This schema should be implemented with **Pydantic models** and **strong typing throughout**.

### File node

At minimum:

- `file_path`
- `language`
- `node_id` or canonical key
- optional summary stats:
  - `out_degree`
  - `in_degree`
  - evidence counts

Recommended additions:

- stable repository-relative id
- extractor metadata
- deterministic sort key
- validation helpers

### Structural edge

At minimum:

- `source_file`
- `target_file`
- `structural_basis`
- `evidence_relations`
- `evidence_count`
- optional provenance:
  - source symbol
  - target symbol
  - raw relation

Important design choice:

- structural graph must stay security-neutral
- no `attack_type` or `edge_attack_cost` in this phase

### Graph artifact

Add a typed top-level artifact model containing:

- graph metadata
- file nodes
- structural edges
- summary counts
- extraction diagnostics
- projection diagnostics

## Phase 4 — Implement the file-graph projector

This is the core of the first milestone.

The projector should:

- enumerate all CodeGraph file nodes
- map symbol nodes back to owning files
- collapse symbol-level relations into file-level edges
- deduplicate edges
- aggregate evidence

### First-pass edge rules

Start with these:

- `imports_symbol`
  - file A imports symbol in file B
  - emit structural edge `A -> B`

- `uses_symbol` / calls-style symbol relations
  - symbol in file A uses symbol in file B
  - emit structural edge `A -> B`

- file-to-symbol ownership edges like `defines` / `exports`
  - use these as provenance and input
  - do not emit them as final structural edges by themselves

- self-edges
  - drop by default from exported output
  - keep internal counts for diagnostics if useful

### Output requirements

The projection must be:

- deterministic
- stable-sorted
- explainable
- easy to feed into later attack-edge generation

### Explainability requirements

Every emitted structural edge should preserve enough provenance to answer:

- which raw CodeGraph relation(s) produced this edge?
- which source/target symbols contributed?
- was evidence aggregated or deduplicated?
- why was a candidate edge omitted?

## Phase 5 — Persistence and artifact format

Persist two artifacts separately:

- raw CodeGraph artifact
- projected structural graph artifact

This gives clean recomputation boundaries:

- rebuild projection logic without re-running repo extraction
- inspect raw evidence when structural output looks wrong

Store the structural graph as JSON first.

Artifact requirements:

- deterministic ordering
- stable ids
- explicit schema version
- summary counts that reconcile with serialized contents
- enough provenance to debug edge creation

## Phase 6 — CLI and developer workflow

Add a minimal command that can:

- build a structural graph from a repo
- print summary counts
- save JSON artifact

For MVP, the CLI should answer:

- how many files?
- how many structural edges?
- what relation types contributed?
- what are sample top edges?

The CLI should also emit structured logs and diagnostics rather than only human-formatted text.

## Phase 7 — Error taxonomy, logging, and observability

This work must ship with explicit operational visibility.

### Error taxonomy

Use categorized errors such as:

- configuration error
- repository access error
- extraction error
- projection error
- validation error
- persistence error
- internal invariant violation

### Fail fast, fail loudly

Core invariants must stop the run immediately when violated.

Examples:

- duplicate file ids
- malformed artifact schema
- summary counts that do not match serialized nodes/edges
- structural edges pointing at missing files
- missing provenance where provenance is required by the schema

### Observability requirements

Emit structured observability for at least:

- repository scanned
- files discovered
- files skipped
- candidate relations seen
- structural edges emitted
- structural edges dropped
- deduplication counts
- artifact write/read results
- validation summary
- durations by phase

Observability is part of correctness, not optional polish.

## Phase 8 — Test strategy

Treat the projector as the critical trust boundary.

### Tests to add immediately

- tiny fixture repo with 3-5 files
- assert expected file nodes
- assert expected file-to-file edges
- assert edge aggregation is correct
- assert self-edges are excluded
- assert deterministic JSON output ordering
- assert provenance is preserved on edges
- assert summary counts reconcile with artifact contents

### Language coverage

Since CodeGraph already supports multiple languages, start with:

- Python fixture
- JavaScript or TypeScript fixture

Add more only after the projector is stable.

## Key design decisions to lock in now

### 1. Keep structural and attack graphs separate

This is a core architectural constraint and should be reflected in code immediately.

### 2. Make provenance first-class

Every structural edge should be explainable in terms of underlying CodeGraph evidence.

### 3. Prefer a simple deterministic JSON artifact first

Do not jump straight to database or visualization.

### 4. Do not implement LLM scoring yet

For this branch, the goal is:

- ingest repo
- emit trustworthy structural file graph

That is the correct first slice.

## First milestone definition

A successful first milestone should support:

- input: repository path
- output: `structural_graph.json`

That artifact should contain:

- all source-file nodes
- projected file-to-file structural edges
- relation and evidence metadata
- stable ordering
- enough provenance to debug bad edges

## Risks and unknowns

The main technical risk is that CodeGraph is richer and more symbol-centric than Pathfinder's MVP model.

Likely tricky parts:

- deciding which raw relations count as structural evidence
- avoiding noisy or duplicate file edges
- preserving enough provenance without bloating the graph

That is why the schema and projector tests should come before broad implementation.

## Recommended implementation sequence

1. scaffold the Python package
2. define structural graph models with Pydantic and strong typing
3. implement the CodeGraph adapter
4. implement the projector on a small fixture
5. add CLI and tests
6. validate on one real repo

## Dependency note

Because this repo currently has no Python project setup, the first implementation step will likely require adding Python packaging and dependency management for CodeGraph usage.

Do not hand-edit dependency manifests if a package manager command can express the change.

## Immediate next action

Begin with either:

- package scaffold plus structural graph schema, or
- schema-first, if the team wants to lock the data model before wiring CodeGraph

Given the current principles, **schema-first is slightly preferable** because it sharpens invariants, error handling, observability, and artifact design before integration work begins.