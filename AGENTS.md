# Pathfinder Agent Guide

This file is the grounding contract for coding agents and human contributors working in this repository.

It is derived from:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/PRD.md`
- `docs/GRAPH_SCHEMA.md`

Pathfinder's MVP is:

- **file-first**
- **structural-graph-first**
- **attack-graph-second**
- **bounded-AI**
- **deterministic-after-scoring**
- **fully explainable**

---

## 1. Core mission

Build the smallest real thing that answers:

> Given a codebase, what is the most likely path an attacker would take through the code?

For MVP:

- nodes are **files**
- the first graph is the **structural file graph**
- attack transitions are derived **from** structural evidence
- path search is deterministic **after** scoring

Do not drift into:

- service inference
- runtime or infrastructure modeling
- CVE ingestion
- goal-conditioned search
- autonomous remediation

If a change does not strengthen the file-graph MVP, it is probably out of scope.

---

## 2. Ground truth rules

### 2.1 Structural extraction is authoritative

- Structural edges come from extracted code relationships.
- LLMs do **not** invent structural edges.
- Attack edges may only be derived from existing structural edges.
- If evidence is weak or missing, emit uncertainty or omit the result.

### 2.2 Keep graph layers separate

Maintain clear boundaries between:

1. raw extraction layer
2. structural file graph
3. attack graph
4. search and explanation outputs

Do not merge these layers for convenience.

### 2.3 Files are the canonical MVP node

- files are nodes
- `entry`, `transition`, and `target` are roles, not node types
- `target_flag` is a property on a file node

Symbol-level detail may exist internally, but it must support file-level outputs, not replace them.

---

## 3. Determinism and explainability

### 3.1 Deterministic after scoring

Once node and edge scores exist:

- traversal must be deterministic
- ranking must be repeatable
- output ordering should be stable
- serialization should be stable where practical

The LLM is not part of online path search.

### 3.2 Explain everything important

Every meaningful output must be traceable to:

- real files
- real structural edges
- real attack edges
- real scores
- real rationales

If an output cannot be explained, it is not ready.

### 3.3 Provenance is first-class

Preserve provenance for every derived artifact.

Examples:

- a structural edge should record its extractor and evidence
- an attack edge should reference the structural edge(s) that justify it
- a ranked path should reference the nodes and edges actually used

---

## 4. AI usage rules

### 4.1 Bounded AI only

For MVP:

- one LLM pass per file for target/risk analysis
- one LLM pass per structural edge for attack-edge derivation
- no LLM use in deterministic path search

### 4.2 AI scores; it does not author reality

The model may:

- classify target-like files
- assign node risk
- decide whether a structural edge supports a plausible attack transition
- label attack type and traversal cost
- generate grounded explanations

The model may not:

- invent files
- invent dependencies
- emit attack edges without structural basis
- bypass schema constraints

### 4.3 Prefer constrained outputs

Where AI is used:

- prefer schemas over free-form text
- normalize numeric values where applicable
- prefer enums over open-ended category strings
- keep rationales short and evidence-oriented

---

## 5. Engineering design principles

### 5.1 SOLID by default

- keep responsibilities narrow
- isolate external systems behind adapters
- keep core domain models independent from transport or SDK details
- favor composition over monoliths

### 5.2 Small modular files

Prefer small files with one clear purpose.

Guidelines:

- one major responsibility per file
- split files before they become hard to scan
- keep models, adapters, orchestration, CLI, and presentation separate
- optimize for fast comprehension by humans and coding agents

If a file mixes unrelated concerns or multiple architecture layers, split it.

### 5.3 Explicit schemas over ad hoc dictionaries

Use typed models for core artifacts.

Use **Pydantic schemas** for boundary-facing and persisted data models.

Default to:

- Pydantic models for repository configs, graph artifacts, summaries, diagnostics, and API payloads
- explicit field types and validation rules
- enums or literals for constrained categories
- explicit serialization instead of passing raw dictionaries through the system

At minimum, define explicit types for:

- file nodes
- structural edges
- attack edges
- summaries and diagnostics
- extraction/search results
- errors

### 5.4 Strong typing throughout the codebase

Prefer strong static typing throughout the codebase, not just at external boundaries.

Guidelines:

- type all function signatures
- avoid `Any` unless there is a narrow, unavoidable boundary
- prefer typed domain objects over `dict[str, Any]`
- use `Path` for filesystem paths where appropriate
- make nullability explicit
- use protocols or interfaces at subsystem boundaries when helpful

Validation should happen at ingress, strongly typed objects should be used internally, and serialization should happen explicitly at egress.

### 5.5 Composition over hidden coupling

Good:

- extractor -> projector -> validator -> serializer

Bad:

- one opaque function that ingests, scores, searches, explains, and writes artifacts in one pass

---

## 6. Observability is truth

If the system cannot be inspected, it cannot be trusted.

### 6.1 Structured logging by default

Logs should be structured and useful.

Every important event should aim to include:

- event name
- phase or module
- repository or artifact id
- counts and durations
- key decision fields
- error category when relevant

Avoid vague string-only logs.

### 6.2 Metrics and artifacts must reconcile

If logs or summaries say:

- 52 files extracted
- 141 structural edges emitted

then serialized artifacts must support those numbers.

Mismatch between logs, summaries, and artifacts is a correctness bug.

### 6.3 Make silent dropping visible

Whenever data is:

- omitted
- filtered
- deduplicated
- downgraded

that must be counted and exposed.

Silent data loss destroys trust.

---

## 7. Error handling rules

### 7.1 Fail fast, fail loudly

Do not bury invariant violations, schema breakage, or contradictory state.

- fail early when a core assumption is broken
- fail with a clear category and context
- do not silently continue past integrity violations
- do not convert correctness failures into fake success

If something is wrong with the graph, the counts, the ids, or the provenance, surface it immediately.

### 7.2 Use an explicit error taxonomy

Prefer categorized errors such as:

- configuration error
- repository access error
- extraction error
- projection error
- validation error
- persistence error
- scoring error
- search error
- external dependency error
- internal invariant violation

### 7.3 Preserve context in errors

Errors should carry actionable context:

- repository path
- file path
- node or edge id
- operation name
- upstream cause
- recoverability hint when available

---

## 8. Data and artifact rules

### 8.1 Stable identifiers matter

Use stable repository-relative paths and deterministic ids wherever possible.

This supports:

- reproducibility
- diffability
- cacheability
- future incremental workflows

### 8.2 Persist phase boundaries

Keep separate artifacts for separate phases when possible:

- raw extraction artifact
- structural graph artifact
- attack graph artifact
- path analysis artifact

### 8.3 Artifacts should be reviewable

Outputs should be readable enough for debugging and technical review.

Prefer:

- deterministic ordering
- summary metadata
- provenance references
- validation hooks

---

## 9. Testing and validation rules

### 9.1 Test projection rules directly

The structural projector is a core trust boundary.

Tests should cover:

- expected nodes
- expected edges
- deduplication behavior
- self-edge policy
- ordering stability
- provenance preservation

### 9.2 Small fixtures first

Start with tiny repositories and obvious dependency cases before scaling up.

### 9.3 Summaries are part of correctness

Counts, diagnostics, and observability outputs are testable outputs.

If summaries are wrong, the system is wrong.

---

## 10. Coding-agent operating rules

### 10.1 Read the architecture before changing the architecture

Before implementing or extending a subsystem, align with:

- file-first MVP scope
- structural-vs-attack separation
- deterministic-after-scoring behavior
- explainability requirements

### 10.2 Do not smuggle product decisions through convenience code

Unacceptable drift includes:

- merging structural and attack edges into one type for convenience
- hiding provenance because the model seems good enough
- replacing constrained output with free-form heuristics without justification

### 10.3 Prefer explicitness over magic

Prefer:

- named transformation steps
- typed models
- clear logs
- explicit defaults
- documented assumptions

over:

- hidden globals
- implicit mutation
- silent fallback behavior
- undocumented heuristics

### 10.4 Leave the system easier to inspect than you found it

Good changes improve at least one of:

- traceability
- schema clarity
- testability
- observability
- determinism
- operator understanding

---

## 11. Non-negotiables

- Do not invent structural connectivity.
- Do not emit attack edges without structural basis.
- Do not use LLMs for deterministic path search.
- Do not hide provenance.
- Do not ship opaque outputs that cannot be explained.
- Do not let logs, summaries, and artifacts disagree.
- Do not trade correctness for demo polish.

If forced to choose, Pathfinder must prefer grounded truth over attractive uncertainty.