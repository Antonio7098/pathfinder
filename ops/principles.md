# Pathfinder Engineering Principles

This document is the grounding contract for coding agents and human contributors working on Pathfinder.

It is derived from:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/PRD.md`
- `docs/GRAPH_SCHEMA.md`

The goal is to keep implementation aligned with Pathfinder's MVP: a file-level structural graph, attack-transition derivation, bounded AI analysis, deterministic search, and explainable outputs.

---

## 1. Mission and Scope

### 1.1 Build the smallest real thing

Pathfinder's MVP is intentionally narrow.

- The unit of reasoning is the **file**.
- The first graph is the **structural file graph**.
- Attack semantics are added **after** structure exists.
- Search is deterministic **after** scoring.

Agents must resist scope creep into:

- service inference
- infrastructure/runtime modeling
- vulnerability ingestion
- goal-conditioned search
- autonomous remediation

If a change does not strengthen the file-graph MVP, it is probably out of scope.

### 1.2 Build for truth, not impressiveness

Pathfinder must prefer grounded, boring, inspectable outputs over flashy but weakly justified ones.

- Real files beat inferred abstractions.
- Real extracted edges beat speculative connectivity.
- Explicit provenance beats opaque convenience.
- Repeatable behavior beats clever hidden heuristics.

---

## 2. Architectural Principles

### 2.1 Structural graph first

Structural extraction is authoritative for graph connectivity.

- Structural edges come from extracted code relationships.
- LLMs do **not** invent structural edges.
- If structure is uncertain, emit uncertainty or omit the edge.
- Attack reasoning may only operate on existing structural evidence.

### 2.2 Keep graph layers separate

Pathfinder has distinct graph layers with distinct responsibilities.

1. **Raw extraction layer**: repository-derived graph data from CodeGraph or equivalent.
2. **Structural file graph**: files and file-to-file evidence-backed relationships.
3. **Attack graph**: plausible attacker transitions derived from structural edges.
4. **Search/output layer**: ranked paths, choke points, explanations.

Do not collapse these layers into one ambiguous model.

### 2.3 Files are the canonical MVP node

For MVP:

- nodes are files
- entry/transition/target are **roles**, not node types
- `target_flag` is a file property, not a separate class of object

If symbol-level detail is used internally, it must support file-level outputs rather than leak accidental complexity into the public model.

### 2.4 Deterministic after scoring

Once node and edge scores are assigned:

- graph traversal must be deterministic
- ranking must be repeatable
- output ordering must be stable
- serialization must be stable where practical

The LLM is used for bounded scoring and labeling, not for online path search.

---

## 3. Explainability Principles

### 3.1 Every meaningful output must be explainable

Every predicted path, risky file, or recommended mitigation must be traceable to:

- real files
- real structural edges
- real attack-transition edges
- real scores
- real rationales

### 3.2 Provenance is a first-class feature

Every derived artifact should preserve its basis.

Examples:

- a structural edge should record the extractor and supporting evidence
- an attack edge should cite the structural edge(s) it came from
- a ranked path should reference the specific nodes and edges used in scoring

If an output cannot be explained, it is not ready to ship.

### 3.3 Never hide lossy transformations

When collapsing richer source data into file-level outputs:

- document the projection rules
- preserve enough provenance to debug the projection
- make omission rules explicit
- prefer reversible or inspectable transformations when possible

---

## 4. AI Usage Principles

### 4.1 AI is bounded and controlled

For MVP:

- one LLM pass per file for target/risk analysis
- one LLM pass per structural edge for attack-edge derivation
- no LLM in deterministic path search

### 4.2 AI scores; it does not author reality

The model may:

- classify files as likely targets
- assign node risk
- decide whether a structural edge supports a plausible attack transition
- label attack type and traversal cost
- generate human-readable explanations grounded in evidence

The model may not:

- invent files
- invent unsupported structural dependencies
- emit attack edges without structural basis
- bypass schema constraints

### 4.3 Prefer constrained outputs

Where AI is used:

- outputs should be schema-constrained
- numeric values should be normalized where applicable
- enums should be preferred over free-form categories
- rationales should be short and evidence-oriented

---

## 5. SOLID and System Design Principles

### 5.1 Single responsibility by layer

Keep responsibilities narrow.

- adapters ingest external systems
- projectors transform one graph form into another
- scorers assign scores
- search modules rank paths
- renderers/explainers prepare output

Avoid god objects and monolithic pipelines.

### 5.2 Dependency inversion at boundaries

Core Pathfinder logic should depend on interfaces or internal domain models, not directly on external SDK details.

Examples:

- isolate CodeGraph access behind an adapter
- keep domain models independent from external transport formats
- make scoring and persistence swappable at the boundary

### 5.3 Explicit schemas over ad hoc dictionaries

Use typed models for core artifacts.

At minimum, define explicit types for:

- file nodes
- structural edges
- attack edges
- graph summaries
- extraction/scoring/search results
- errors and diagnostics

### 5.4 Composition over hidden coupling

Prefer small composable components that can be tested independently.

Good:

- extractor -> projector -> validator -> serializer

Bad:

- one opaque function that builds, scores, searches, explains, and writes files in one pass

### 5.5 Small modular files

Prefer small files with a clear purpose over large catch-all modules.

Guidelines:

- one major concept or responsibility per file
- keep public interfaces near the top and helper detail below
- split files before they become hard to scan or review
- separate domain models, adapters, orchestration, and CLI concerns
- optimize for fast comprehension by humans and coding agents

As a rule of thumb, if a file starts mixing unrelated responsibilities, hidden state, or multiple layers of the architecture, it should probably be split.

---

## 6. Observability Principles

### 6.1 Observability is truth

If the system's behavior cannot be inspected, it cannot be trusted.

Every major operation should emit structured observability signals.

Examples:

- repository scanned
- files discovered
- files skipped
- edges emitted
- edges collapsed/deduplicated
- validation failures
- scoring counts
- search statistics
- artifact write/read outcomes

### 6.2 Structured logging by default

Logs should be structured, machine-parseable, and useful for humans.

Every meaningful log event should aim to include:

- event name
- phase/module
- repository or artifact identifier
- counts and durations
- key decision fields
- error category when relevant

Avoid vague string-only logs.

### 6.3 Metrics and summaries should match artifacts

Observability must reconcile with persisted outputs.

If a summary says:

- 52 files extracted
- 141 structural edges emitted

then the artifact should support those numbers.

Mismatch between logs, summaries, and serialized artifacts is a correctness bug.

### 6.4 Make silent dropping visible

Whenever data is omitted, filtered, deduplicated, or downgraded:

- count it
- expose it
- explain why

Silent data loss destroys trust.

---

## 7. Error Taxonomy Principles

### 7.1 Errors must be categorized

Do not surface undifferentiated failures when a category is knowable.

Use a clear taxonomy such as:

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

### 7.2 Errors should preserve context

Errors should carry actionable context, such as:

- repository path
- file path
- edge or node identifier
- operation name
- upstream cause
- recoverability hint

### 7.3 Favor partial diagnostics over black-box failure

When safe and appropriate, return diagnostics with partial results rather than only failing generically.

But do not silently convert integrity failures into success.

### 7.4 Invariants must fail loudly

If a core invariant is violated, the system should stop and make the violation explicit.

Examples:

- attack edge references missing structural basis
- file node ids are unstable or duplicated
- artifact schema is malformed
- summary counts do not match serialized contents

---

## 8. Data and Artifact Principles

### 8.1 Stable identifiers matter

Use stable repository-relative paths and deterministic ids wherever possible.

This supports:

- reproducibility
- diffability
- cacheability
- future incremental updates

### 8.2 Persist phase boundaries

Important pipeline stages should have explicit artifact boundaries.

At minimum, keep separate concepts for:

- raw extraction artifact
- structural graph artifact
- attack graph artifact
- path analysis artifact

### 8.3 Artifacts should be reviewable

Serialized outputs should be readable enough for debugging and technical review.

Prefer formats that support:

- deterministic ordering
- summary metadata
- provenance references
- validation

---

## 9. Validation and Testing Principles

### 9.1 Test the projection rules directly

The file-graph projector is a core trust boundary.

Tests should cover:

- expected nodes
- expected edges
- deduplication behavior
- self-edge policy
- ordering stability
- provenance preservation

### 9.2 Small fixtures first

Use tiny repositories to validate semantics before trying large real repos.

Start with:

- 3-5 file fixtures
- clear imports/calls/references
- cross-file and same-file cases
- ambiguous/noisy cases

### 9.3 Treat summaries as testable outputs

Counts, diagnostics, and observability summaries are part of correctness.

If summaries are wrong, the system is wrong.

### 9.4 Prefer trustworthy behavior over broad coverage

It is better to support a smaller set of structural relationships correctly than to overclaim broad capability with noisy edges.

---

## 10. Coding-Agent Operating Rules

### 10.1 Read the architecture before changing the architecture

Before implementing or extending a subsystem, agents must align with:

- file-first MVP scope
- structural-vs-attack graph separation
- deterministic-after-scoring behavior
- explainability requirements

### 10.2 Do not smuggle in product decisions through convenience code

If a coding shortcut changes product semantics, it is not a shortcut.

Examples of unacceptable drift:

- merging structural and attack edges into one type for convenience
- hiding provenance because the model is "good enough"
- using free-form AI output when schema-constrained output is required

### 10.3 Prefer explicitness over magic

Agents should prefer:

- named transformation steps
- typed data models
- clear logs
- explicit defaults
- documented assumptions

over:

- hidden globals
- implicit mutation
- silent fallback behavior
- undocumented heuristics

### 10.4 Leave the system easier to inspect than you found it

Good contributions improve at least one of:

- traceability
- schema clarity
- testability
- observability
- determinism
- operator understanding

---

## 11. Decision Heuristics

When choosing between two designs, prefer the one that is:

1. more grounded in extracted evidence
2. easier to explain to a technical reviewer
3. more deterministic after scoring
4. easier to observe and debug
5. less coupled to a specific external tool
6. more faithful to the file-level MVP

---

## 12. Non-Negotiables

These are hard constraints for the MVP.

- Do not invent structural connectivity.
- Do not emit attack edges without structural basis.
- Do not use LLMs for deterministic path search.
- Do not hide provenance.
- Do not ship opaque outputs that cannot be explained.
- Do not let logs, summaries, and artifacts disagree.
- Do not trade correctness for demo polish.

If forced to choose, Pathfinder should always prefer grounded truth over attractive uncertainty.