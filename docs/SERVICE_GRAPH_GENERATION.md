# Service-Based Graph Generation

## Purpose

This document describes Pathfinder's current **service-based graph generation** flow.

It explains:

* what the service graph is
* how it is generated from the canonical structural graph
* where the LLM is used
* where deterministic logic is used
* what artifacts are produced
* what invariants Pathfinder enforces

Related docs:

* `docs/ARCHITECTURE.md`
* `docs/GRAPH_SCHEMA.md`
* `docs/STRUCTURAL_GRAPH_EXTRACTION.md`
* `docs/SERVICE_GROUPING.md`

---

## Core design rule

The service graph is a **derived overlay**, not the canonical graph.

Pathfinder still treats the file-level structural graph as authoritative:

* files remain the extracted ground-truth nodes
* structural edges remain the extracted ground-truth relationships
* the LLM may group files into services
* the LLM may not invent service connectivity
* service-to-service edges are derived algorithmically from file-level structural edges

This preserves the current file-first MVP while allowing a more scalable graph for higher-level reasoning.

---

## High-level pipeline

The current implemented pipeline is:

1. build a file-level structural graph from a repository
2. send the structural graph summary to an LLM for grounded service grouping
3. validate and deterministically resolve file-to-service assignments
4. build a service graph by aggregating file-level structural edges across service boundaries
5. persist both the grouping artifact and the service graph artifact

In code, the main pieces are:

* `pathfinder/services/service.py`
* `pathfinder/services/resolver.py`
* `pathfinder/services/graph_builder.py`
* `pathfinder/services/models.py`
* `pathfinder/llm/prompts/service_grouping.py`
* `pathfinder/llm/prompts/service_grouping_v1.py`

---

## Phase 1: service grouping

### LLM input

The service-grouping prompt is built from the structural graph and currently includes:

* repository path
* graph id
* structural summary counts
* file list with language and degree metadata
* structural edge list with relationship type and evidence count
* directory summaries
* directory-to-directory relationship summaries

If a raw CodeGraph artifact is available, the prompt may also include bounded graphcode evidence such as:

* directory-level symbol summaries
* directory representative files
* selected file profiles with exported symbols and role hints
* top inter-file symbol interaction summaries

This gives the model enough grounded context to propose service boundaries without replacing the file graph.

### Recommended enriched CLI flow

1. Build the structural graph and persist the raw CodeGraph artifact:

   `python -m pathfinder.cli build-structural-graph --repo <repo> --output structural_graph.json --raw-codegraph-output raw_codegraph.json`

2. Run service grouping with that raw artifact:

   `python -m pathfinder.cli identify-services --input structural_graph.json --raw-codegraph raw_codegraph.json --output service_grouping.json`

This enriched path gives the classifier more grounded architectural evidence without turning the raw CodeGraph export into a hidden source of truth.

### LLM output

The model returns a structured payload containing:

* `architecture_summary`
* `services`
* `shared_file_paths`
* `unclassified_file_paths`

Each proposed service includes:

* service name
* service layer
* summary
* member file paths
* confidence
* rationale

### What the LLM is allowed to do

The LLM may:

* group known files into service candidates
* assign a layer label to each service
* mark clearly cross-cutting files as shared
* leave hard cases unclassified

The LLM may not:

* invent file paths
* invent structural edges
* invent service-to-service edges
* bypass artifact validation

---

## Phase 2: deterministic assignment resolution

The LLM output is not accepted raw.

Pathfinder runs a deterministic resolver that:

* rejects invented file references
* drops empty services
* assigns multiply-claimed files to a shared bucket
* preserves explicit shared assignments
* records explicit unclassified assignments
* promotes omitted files to a grounded inferred service when structural connectivity strongly supports that move
* promotes omitted files by directory evidence when a nearby grounded cluster is obvious
* creates deterministic residual cluster services for coherent leftover top-level groups such as `tests/`, `frontend/`, or `backend/`
* places any remaining files into an unclassified bucket

This keeps the overlay usable on real repositories without turning the LLM into the source of truth.

### Resolution sources

Each file assignment records how it was decided.

Current sources include:

* `llm_primary`
* `explicit_shared`
* `explicit_unclassified`
* `overlap_shared`
* `connectivity_primary`
* `directory_primary`
* `cluster_primary`
* `fallback_unclassified`

---

## Phase 3: service graph derivation

Once every file has a service assignment, Pathfinder builds the service graph deterministically.

For each structural edge:

* look up the source file's assigned service
* look up the target file's assigned service
* if both files map to the same service, count it as an internal structural edge
* if they map to different services, aggregate it into a service edge

Each service edge records:

* `source`
* `target`
* aggregated `relationship_types`
* `supporting_structural_edge_ids`
* `supporting_file_pairs`
* `supporting_edge_count`

This is the key trust boundary: **service edges are always grounded in real structural edges**.

---

## Artifacts

### `ServiceGroupingArtifact`

This artifact stores:

* grounded service definitions
* file-to-service assignments
* prompt/model invocation metadata
* summary counts
* diagnostics for invented paths, overlaps, promoted files, and dropped services

### `ServiceGraphArtifact`

This artifact stores:

* service graph nodes
* service graph edges
* summary counts
* derivation diagnostics

The grouping artifact is the classification boundary.

The service graph artifact is the deterministic graph boundary.

---

## Service node shape

Service graph nodes currently include:

* `id`
* `name`
* `kind`
* `layer`
* `summary`
* `member_file_paths`
* `file_count`
* `files_by_language`
* `confidence`
* `rationale`

This means a service node is never just a label. It always remains traceable to concrete file membership.

---

## Validation and invariants

The current implementation fails fast on integrity errors.

Examples:

* every known file must receive exactly one assignment
* service member files must reconcile exactly with assignments
* service ids must be unique
* service graph nodes must be unique
* service graph edges must reference real service nodes
* grouping artifacts must match the structural graph they are paired with
* summary counts must reconcile with serialized artifact content

---

## CLI flow

### 1. Build the structural graph

`python -m pathfinder.cli build-structural-graph --repo <repo> --output structural_graph.json`

### 2. Identify services

`python -m pathfinder.cli identify-services --input structural_graph.json --output service_grouping.json`

Useful runtime controls:

* `--timeout-seconds`
* `--model`
* `--max-output-tokens`
* `--raw-codegraph`

### 3. Build the derived service graph

`python -m pathfinder.cli build-service-graph --structural-graph structural_graph.json --grouping service_grouping.json --output service_graph.json`

---

## Current limitations

This is a service overlay, not a replacement search model.

Current limits:

* the canonical Pathfinder MVP remains file-first
* service grouping quality still depends partly on model quality
* the service graph is not yet wired into attack-edge derivation or path ranking
* some repos may produce deterministic residual clusters where the model does not supply a clean service taxonomy

These limits are intentional for now.

---

## Practical interpretation

Today, the service graph should be understood as:

* a more scalable architectural view of the repository
* grounded in the structural file graph
* partially proposed by the LLM
* made deterministic after grouping
* fully explainable through file membership and supporting structural edges

That is the current contract for service-based graph generation in Pathfinder.