# Structural Graph Extraction Execution Report

## Phase summary

This report covers the implementation and validation of Pathfinder's structural graph extraction phase.

Scope for this phase was intentionally narrow:

- files are the unit of reasoning
- structural graph extraction comes before attack-edge derivation
- structural evidence remains separate from attack semantics
- outputs must be deterministic, typed, observable, and explainable

The phase was executed on branch `feat/structural-graph-extraction`.

## Objectives

The phase set out to deliver:

1. a Pathfinder Python package scaffold
2. a CodeGraph adapter using `ucp-content`
3. a typed structural graph schema
4. a deterministic file-to-file structural projector
5. JSON artifact persistence
6. a CLI for structural extraction
7. tests and real-repository validation

## Implemented deliverables

### Package and interfaces

Added a Python package with clear module boundaries:

- `pathfinder/adapters/`
- `pathfinder/observability/`
- `pathfinder/structural/`
- `pathfinder/cli.py`
- `pathfinder/errors.py`
- `pyproject.toml`

### Typed schemas and strong typing

Implemented Pydantic-backed models for:

- raw CodeGraph document blocks and edges
- structural graph nodes and edges
- provenance records
- diagnostics and summaries
- extraction requests and results

### Error taxonomy and fail-fast behavior

Implemented explicit categorized errors for:

- configuration
- repository access
- extraction
- projection
- validation
- persistence
- internal invariants

Artifact validation fails loudly on broken invariants such as:

- duplicate file ids
- missing node references in edges
- summary count mismatches

### Observability and explainability

Implemented structured JSON logging for major lifecycle events, including:

- extraction start/end
- CodeGraph build start/end
- raw graph persistence
- structural projection completion

Every structural edge preserves provenance back to underlying CodeGraph evidence.

### Structural projection logic

Implemented a file-level projector that:

- enumerates file and symbol blocks
- maps symbols back to owning files
- projects symbol/file relations into file-to-file structural edges
- deduplicates evidence
- drops self-edges
- records omitted relations in diagnostics

Current supported structural mappings:

- `imports` -> `imports`
- `imports_symbol` -> `imports`
- `reexports` -> `imports`
- `uses_symbol` -> `calls`
- `extends` -> `references`
- `implements` -> `references`

Relations intentionally left out for this phase:

- `exports`
- `for_type`

These were omitted because they are primarily ownership/provenance signals rather than high-value cross-file structural dependencies.

## Tuning work performed

The extractor was not left at fixture-only quality. It was reviewed and tuned against multiple real repositories.

### Key tuning changes

1. mapped `reexports` into structural `imports`
2. expanded default excluded directories to reduce environment and generated-file noise

Added default excludes for directories such as:

- `.venv`
- `venv`
- `__pycache__`
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `.tox`
- `.next`
- `.turbo`
- `coverage`

### Why the `reexports` change mattered

Many real repositories use:

- TypeScript barrel files
- Python package `__init__.py` reexports

Without this mapping, the graph under-represented real file-level structure. The change increased retained evidence without increasing emitted edge counts.

## Validation performed

### Automated tests

The final test run used:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`

Result:

- `8 passed`

Plugin autoload was disabled because of an environment-level global pytest plugin conflict unrelated to Pathfinder's code.

### Fixture coverage

Added and validated fixtures for:

- basic Python imports/calls
- self-edge exclusion
- TypeScript imports/calls
- Python reexports
- TypeScript reexports
- generated/environment directories excluded by default

### Real-repository smoke validation

Structural extraction was run successfully against:

- `/home/antonio/df-frontier/aviva/Tech_Task/aviva-claims-mail-intelligence-sprint-08`
- `/home/antonio/programming/Hivemind/hivemind-frontend`
- `/home/antonio/programming/Hivemind/unified-content-protocol`
- `/home/antonio/programming/sf/stageflow`
- `/home/antonio/programming/voice-engine`

## Measured outcomes

### Aviva claims repo

- files: `79`
- structural edges: `264`
- evidence: `638 -> 710` after tuning
- omitted relations reduced from `{'exports': 189, 'reexports': 72}` to `{'exports': 189}`

### Hivemind frontend

- files: `66`
- structural edges: `251`
- evidence: `547 -> 576` after tuning
- omitted relations reduced from `{'exports': 119, 'reexports': 29}` to `{'exports': 119}`

### Unified Content Protocol

- files: `181`
- structural edges: `316`
- evidence: `2026 -> 2293` after tuning
- omitted relations reduced from `{'exports': 1296, 'for_type': 580, 'reexports': 403}` to `{'exports': 1296, 'for_type': 580}`

### Stageflow

- files: `204`
- structural edges: `773`
- evidence: `3471 -> 3887` after tuning
- omitted relations reduced from `{'exports': 903, 'reexports': 416}` to `{'exports': 903}`

### Voice Engine

- files: `26`
- structural edges: `47`
- evidence: `195 -> 253` after tuning
- omitted relations reduced from `{'exports': 48, 'reexports': 58}` to `{'exports': 48}`

## Quality assessment

This phase achieved its intended outcome.

The structural graph extractor is now:

- typed end to end
- deterministic
- provenance-rich
- observable
- fail-fast on invariants
- validated on both fixtures and real repositories
- tuned to retain more real structural evidence without graph explosion

## Out of scope for this phase

The following were intentionally not implemented:

- attack-edge derivation
- per-file AI risk/target analysis
- path ranking over attack transitions
- language-specific heuristic weighting beyond conservative structural mapping

## Recommended next step

Freeze this phase as the completed structural foundation.

Future work should build on the structural graph artifact rather than re-opening structural extraction unless a clearly justified language- or relation-specific gap is discovered.