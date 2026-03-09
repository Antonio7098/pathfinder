# Pathfinder

**AI that reduces cyber threat analysis from hours to seconds.**

Pathfinder is an AI-accelerated cybersecurity platform designed to reduce **MTTR — Mean Time To Respond**.

Instead of only listing vulnerabilities, Pathfinder helps answer the question:

> If a vulnerability appears in this system, how would an attacker most likely move through it, and what should we fix first?

## Why Pathfinder

Security teams often spend too long on three things:

* discovering what part of the system is actually affected
* understanding likely attack paths
* deciding the best mitigation point

Pathfinder is built to shrink those delays by combining:

* **code-derived structural file-graph extraction**
* **deterministic graph reasoning**
* **LLM-based file and edge analysis**

## Core value proposition

Pathfinder is not just an "LLM for security."

It is a hybrid system that:

1. builds a structural graph of source files and their relationships
2. runs one LLM analysis per file to identify likely target files and assign node risk
3. runs one LLM analysis per structural edge to derive attack edges and traversal cost
4. ranks likely attacker paths from entry-like files to target files
5. identifies choke points and recommends mitigations

This reframes the product from:

*"a tool that predicts attack paths"*

to:

*"an AI system that reduces the time required to understand and respond to cyber threats."*

## How it works

Pathfinder uses a layered file-level graph model:

`Repository → Structural File Graph → Attack Graph`

High-level flow:

1. **Structural extraction** captures source files and file-to-file relationships.
2. **Per-file LLM analysis** assigns `target_flag` and node risk for each file.
3. **Per-structural-edge LLM analysis** derives attack edges and traversal cost.
4. **Attack path search** ranks likely attacker paths deterministically once scores are assigned.
5. **Explanation** highlights why the destination matters and where to mitigate first.

## MTTR-first design

Pathfinder is designed to reduce:

* **threat discovery time**
* **attack path analysis time**
* **mitigation decision time**

Example workflow:

`Repository ingested → Structural graph built → File/edge LLM analysis runs → Attack path ranked → Choke points explained`

## Example outcome

Input:

`Repository contains exposed auth logic, admin routes, and permissions storage`

Output:

`auth_handler.py → session_manager.py → admin_access.py → permissions_store.py`

Recommended action:

`Harden auth_handler.py first; inspect authorization in admin_access.py`

## Key capabilities

* code-derived structural file-graph extraction
* file-level attack path prediction
* target-file risk ranking
* defensive choke-point identification
* explainable mitigation recommendations
* attack-edge reasoning grounded in structural evidence

## Repository contents

This repository now contains a working **structural graph extraction slice** for Pathfinder, alongside the broader product and architecture docs for later phases.

Key docs:

* `docs/PRD.md` — product framing, MVP scope, shipped structural phase, and later phases
* `docs/ARCHITECTURE.md` — technical design, current structural architecture, and later attack-graph layers
* `docs/GRAPH_SCHEMA.md` — schema guidance for the current structural artifact and later attack-graph extensions
* `docs/STRUCTURAL_GRAPH_EXTRACTION.md` — implementation-focused reference for the shipped structural graph phase

## Current repository structure

Current top-level layout:

* `pathfinder/` — Python package
  * `adapters/` — CodeGraph integration and typed raw extractor models
  * `structural/` — structural graph models, projection, I/O, and service layer
  * `viewer/` — minimal frontend assets and HTTP server
  * `observability/` — structured logging helpers
  * `cli.py` — CLI entrypoint
  * `errors.py` — error taxonomy
* `tests/` — fixture repos and automated tests
* `docs/` — product, architecture, schema, and implementation docs
* `ops/` — plans, reports, reviews, rubric assets, and operational reference material
* `AGENTS.md` — canonical coding-agent instructions
* `pyproject.toml` — packaging and test configuration

## Current status

Pathfinder has now shipped its **structural graph foundation**.

Implemented today:

* repository ingestion via CodeGraph / `ucp-content`
* file-level structural graph projection
* deterministic JSON artifact generation
* provenance-rich structural edges and diagnostics
* a minimal frontend for viewing structural graph artifacts

Still planned for later phases:

* per-file LLM target/risk analysis
* per-structural-edge attack-edge derivation
* deterministic path ranking over attack edges
* mitigation and choke-point recommendations

## Current implementation slice

Pathfinder now includes:

* structural graph extraction on top of CodeGraph
* deterministic JSON artifact generation
* a minimal frontend for viewing structural graph artifacts
* structured logging, explicit error taxonomy, and fail-fast artifact validation
* tested fixtures plus real-repository validation

Example commands:

* `python -m pathfinder.cli build-structural-graph --repo <repo> --output structural_graph.json`
* `python -m pathfinder.cli serve-graph-viewer --graph structural_graph.json`

The structural artifact currently includes:

* `file` nodes
* `structural_edges`
* empty `attack_edges`
* `summary`
* `diagnostics`

Structural edges preserve provenance back to underlying CodeGraph evidence.

For implementation detail, relation mapping, diagnostics, invariants, and commands, see:

* `docs/STRUCTURAL_GRAPH_EXTRACTION.md`

## Positioning

Pathfinder can be described in one sentence as:

> Pathfinder builds a structural file graph, uses one LLM pass per file to assign `target_flag` and target risk, uses one LLM pass per structural edge to derive attack edges and traversal cost, and then ranks likely attacker paths deterministically.

Today, the implemented slice is the **first clause of that vision**: building and inspecting the structural file graph.

## Next steps

Likely next implementation milestones:

* implement per-file target/risk analysis
* implement per-structural-edge attack-edge generation
* add deterministic path search over attack edges
* expand the viewer from structural inspection toward path explanation
* add a simple dashboard / copilot demo
