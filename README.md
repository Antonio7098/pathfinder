# Pathfinder

Pathfinder is a file-first cybersecurity analysis system aimed at answering:

> Given a codebase, what is the most likely path an attacker would take through the code, and what should be fixed first?

## What is implemented now

This repository currently ships two main capabilities:

* **structural graph extraction** from a repository into a deterministic file-level graph artifact
* **recommendation reporting** that turns an already-selected path plus file context into a grounded mitigation report

It also includes a reusable LLM layer for future Pathfinder phases.

## What is not implemented yet

These later phases are still planned:

* per-file target/risk analysis
* per-structural-edge attack-edge derivation
* deterministic path search over attack edges
* automatic generation of the selected path artifact that feeds the report step

## Current architecture shape

Pathfinder keeps its layers separate:

* raw extraction
* structural file graph
* attack graph
* deterministic path search
* recommendation reporting

In the current repo, the implemented pieces are the structural graph layer and the post-path reporting layer.

## Main commands

Build a structural graph:

* `python -m pathfinder.cli build-structural-graph --repo /path/to/repo --output structural_graph.json`

Optionally also persist raw CodeGraph output:

* `python -m pathfinder.cli build-structural-graph --repo /path/to/repo --output structural_graph.json --raw-codegraph-output raw_codegraph.json`

Generate a recommendation report from a path input artifact:

* `python -m pathfinder.cli generate-recommendation-report --input recommendation_input.json --output recommendation_report.json`

## Output artifacts

### Structural graph

The structural graph artifact contains:

* `file` nodes
* `structural_edges`
* empty `attack_edges`
* `summary`
* `diagnostics`

### Recommendation report

The recommendation flow consumes a versioned input artifact containing:

* ordered path nodes
* ordered path edges
* focal files

and produces a versioned report artifact containing:

* path overview
* prioritized recommendations
* mitigation steps
* diagnostics
* LLM invocation audit metadata

## LLM usage

The reporting subsystem uses OpenRouter through the OpenAI SDK behind a reusable interface.

Current observability includes:

* prompt template version
* prompt version
* rendered prompts
* prompt hashes
* provider/model metadata
* request id
* token usage when available
* timing and file-context diagnostics

## Repository layout

Important directories:

* `pathfinder/structural/` — structural graph models, projection, I/O, service layer
* `pathfinder/reporting/` — recommendation report models, I/O, and service layer
* `pathfinder/llm/` — reusable LLM abstractions, centralized versioned prompts, and OpenRouter adapter
* `pathfinder/observability/` — structured logging helpers
* `tests/` — fixtures and automated tests
* `docs/` — product, architecture, schema, and implementation docs

## Key docs

* `docs/ARCHITECTURE.md` — architecture and phase boundaries
* `docs/GRAPH_SCHEMA.md` — structural graph schema guidance
* `docs/STRUCTURAL_GRAPH_EXTRACTION.md` — structural extraction implementation details
* `docs/RECOMMENDATION_REPORTING.md` — report input/output artifacts, prompts, observability, CLI usage
* `docs/ENGINEERING_CONVENTIONS.md` — logging, errors, typing, and validation rules
* `docs/PRD.md` — product framing and roadmap

## Current one-line summary

Today, Pathfinder can build a structural file graph and generate a grounded mitigation report once an upstream step has already selected the path to analyze.
