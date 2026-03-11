# Pathfinder

Pathfinder is a file-first cybersecurity analysis system aimed at answering:

> Given a codebase, what is the most likely path an attacker would take through the code, and what should be fixed first?

## What is implemented now

This repository currently ships three main capabilities:

* **structural graph extraction** from a repository into a deterministic file-level graph artifact
* **service grouping + service graph derivation** as an optional overlay built from the structural graph
* **recommendation reporting** that turns an already-selected path plus file context into a grounded mitigation report

It also includes a reusable LLM layer for future Pathfinder phases.

## What is not implemented yet

These later phases are still planned:

* per-file target/risk analysis
* per-structural-edge attack-edge derivation
* deterministic path search over attack edges
* automatic path selection/ranking from scored attack graphs

## Current architecture shape

Pathfinder keeps its layers separate:

* raw extraction
* structural file graph
* attack graph
* deterministic path search
* recommendation reporting

In the current repo, the implemented pieces are the structural graph layer, an optional derived service overlay, and the post-path reporting layer.

## Main commands

Build a structural graph:

* `python -m pathfinder.cli build-structural-graph --repo /path/to/repo --output structural_graph.json`

Optionally also persist raw CodeGraph output:

* `python -m pathfinder.cli build-structural-graph --repo /path/to/repo --output structural_graph.json --raw-codegraph-output raw_codegraph.json`

Generate a recommendation report from a path input artifact:

* `python -m pathfinder.cli generate-recommendation-report --input recommendation_input.json --output recommendation_report.json`

Build a recommendation report input artifact from an existing graph path:

* `python -m pathfinder.cli build-recommendation-input --graph-scope file --structural-graph structural_graph.json --path-node-id web/routes.py --path-node-id pkg/service.py --path-node-id pkg/db.py --output recommendation_input.json`

Build a recommendation report input artifact from a service path while keeping file-grounded evidence:

* `python -m pathfinder.cli build-recommendation-input --graph-scope service --structural-graph structural_graph.json --service-graph service_graph.json --grouping service_grouping.json --path-node-id svc:web --path-node-id svc:app --path-node-id svc:data --output recommendation_input.json`

Infer services from a structural graph artifact:

* `python -m pathfinder.cli identify-services --input structural_graph.json --output service_grouping.json`

Build a deterministic service graph from structural graph + grouping artifacts:

* `python -m pathfinder.cli build-service-graph --structural-graph structural_graph.json --grouping service_grouping.json --output service_graph.json`

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

* `graph_scope` (`file` or `service`)
* ordered path nodes
* ordered path edges
* focal files

In service scope, each path node still carries grounded backing file paths so reporting remains file-evidence-based.

and produces a versioned report artifact containing:

* path overview
* prioritized recommendations
* mitigation steps
* diagnostics
* LLM invocation audit metadata

### Service grouping and service graph overlay

The service overlay adds two versioned artifacts:

* `ServiceGroupingArtifact` — LLM-proposed service groups resolved into grounded file assignments
* `ServiceGraphArtifact` — deterministic service-to-service edges aggregated from structural file edges

These do **not** replace the canonical file-level structural graph.

When the LLM leaves a large cohesive subtree uncovered, Pathfinder may create a deterministic residual cluster service so the overlay stays usable on real repositories without inventing structural connectivity.

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
* `pathfinder/services/` — service grouping models, deterministic service graph derivation, I/O, service layer
* `pathfinder/reporting/` — recommendation report models, I/O, and service layer
* `pathfinder/analysis/` — shared read-only graph adapters for downstream stages that can run on file or service graphs
* `pathfinder/llm/` — reusable LLM abstractions, centralized versioned prompts, and OpenRouter adapter
* `pathfinder/observability/` — structured logging helpers
* `tests/` — fixtures and automated tests
* `docs/` — product, architecture, schema, and implementation docs

## Key docs

* `docs/ARCHITECTURE.md` — architecture and phase boundaries
* `docs/GRAPH_SCHEMA.md` — structural graph schema guidance
* `docs/STRUCTURAL_GRAPH_EXTRACTION.md` — structural extraction implementation details
* `docs/SERVICE_GROUPING.md` — service grouping overlay artifacts, CLI usage, and derivation rules
* `docs/RECOMMENDATION_REPORTING.md` — report input/output artifacts, prompts, observability, CLI usage
* `docs/ENGINEERING_CONVENTIONS.md` — logging, errors, typing, and validation rules
* `docs/PRD.md` — product framing and roadmap

## Current one-line summary

Today, Pathfinder can build a structural file graph, derive an optional service overlay from it, deterministically build report-input artifacts from either graph scope, and generate a grounded mitigation report from that selected path.
