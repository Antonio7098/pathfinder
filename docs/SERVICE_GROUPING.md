# Service Grouping Overlay

## Purpose

Pathfinder now includes an optional **service grouping overlay** built on top of the canonical file-level structural graph.

This layer exists to support more scalable architecture reasoning without changing the file-first MVP contract.

## Key design rule

The structural graph remains authoritative:

* files are still the canonical extracted nodes
* structural edges are still the canonical extracted relationships
* the LLM may propose service groupings only from those known files
* service-to-service edges are derived deterministically from file-level structural edges

The LLM does **not** invent service connectivity.

## Artifacts

### `ServiceGroupingArtifact`

This versioned artifact records:

* grounded inferred services
* file-to-service assignments
* shared and unclassified buckets when needed
* architecture summary
* prompt/model/invocation audit metadata
* diagnostics for invented files, overlaps, and dropped services

### `ServiceGraphArtifact`

This versioned artifact records:

* service nodes derived from the grouping artifact
* inter-service edges aggregated from structural file edges
* supporting structural edge ids and file pairs
* summary counts and diagnostics

## Current CLI commands

Infer a service grouping from a structural graph artifact:

* `python -m pathfinder.cli identify-services --input structural_graph.json --output service_grouping.json`

Infer a service grouping with richer graphcode context:

* `python -m pathfinder.cli identify-services --input structural_graph.json --raw-codegraph raw_codegraph.json --output service_grouping.json`

Build a deterministic service graph from structural graph + service grouping artifacts:

* `python -m pathfinder.cli build-service-graph --structural-graph structural_graph.json --grouping service_grouping.json --output service_graph.json`

## Resolution rules

The current implementation resolves LLM proposals conservatively:

1. unknown file paths are rejected and counted in diagnostics
2. files claimed by multiple inferred services are placed in a shared bucket
3. files omitted by the LLM may be deterministically attached to a grounded inferred service when structural connectivity or directory evidence is strong enough
4. cohesive residual directory groups may be promoted into deterministic cluster services so large leftovers do not collapse into one unclassified bucket
5. any remaining files are placed in an unclassified bucket
6. service ids and output ordering are made deterministic

The deterministic cluster fallback is especially useful for top-level support trees such as `tests/`, `frontend/`, or `backend/` when the LLM leaves a coherent residual subtree uncovered.

## Edge derivation

Service edges are built algorithmically.

If a structural edge connects a file in service A to a file in service B, Pathfinder emits a derived service edge `A -> B` with:

* supporting structural edge ids
* supporting source/target file pairs
* aggregated relationship types

Internal structural edges remain inside the service and are counted in diagnostics rather than emitted as service-to-service edges.

## Runtime controls

The `identify-services` command also accepts:

* `--max-output-tokens`
* `--raw-codegraph`

This bounds the OpenRouter completion size for service grouping. It exists because some models can otherwise over-generate and fail structured parsing on moderate-size repositories.

When `--raw-codegraph` is provided, Pathfinder augments the service-grouping prompt with **bounded graphcode evidence** derived from the raw CodeGraph artifact, including:

* directory-level symbol summaries
* selected file profiles with exported symbols
* grounded role hints such as `api_surface`, `entrypoint`, `migration`, `adapter`, or `graph_pipeline`
* representative files per directory
* top file-pair symbol interaction summaries

This is intentionally curated rather than passing the full raw CodeGraph payload directly into the prompt.