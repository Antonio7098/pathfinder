# Pathfinder Architecture

For the shipped implementation details of the current structural-only phase, see:

* `docs/STRUCTURAL_GRAPH_EXTRACTION.md`
* `docs/ENGINEERING_CONVENTIONS.md`

## Overview

Pathfinder's MVP uses a **file-level attack graph**.

This is a deliberate scope reduction from service-level architecture inference.

The system answers a simpler and more achievable question:

> Given a codebase, what is the most likely path an attacker would take through the code?

The architecture combines:

* **file graph extraction from source code**
* **attack-transition derivation from structural relationships**
* **LLM-based per-file target/risk analysis**
* **LLM-based per-structural-edge attack-edge derivation and cost assignment**
* **deterministic path search**

This is the right MVP shape because it is:

* grounded in explicit code artifacts
* smaller and faster to implement
* easier to explain and demo
* extensible toward richer future models

## Current implementation status

The repository currently implements the **structural graph foundation**, an optional **derived service overlay**, and a **post-path recommendation reporting subsystem**.

Implemented now:

* repository ingestion through CodeGraph / `ucp-content`
* projection from CodeGraph's repository/file/symbol graph into a file-to-file structural graph
* deterministic JSON artifact generation
* provenance-rich structural edges and projection diagnostics
* a versioned service grouping overlay that uses an LLM to group known files into services without changing the canonical structural graph
* a deterministic service graph derivation step that aggregates file-level structural edges into service-to-service edges with provenance
* a reusable `pathfinder.llm` layer for structured LLM calls through OpenRouter via the OpenAI SDK
* a versioned recommendation report pipeline that consumes a selected path input artifact and repository file context
* structured LLM observability for prompt versioning, rendered prompts, model/provider metadata, token usage, and durations

Not yet implemented:

* attack-transition derivation
* LLM file scoring
* LLM edge scoring
* deterministic search over attack edges
* mitigation ranking during path search itself
* automatic production of the selected path input artifact that feeds the report pipeline

---

# High-Level Architecture

```text
Codebase
                    │
                    ▼
      CodeGraph Repository Ingestion     ← implemented
                    │
                    ▼
    File-Level Structural Projection     ← implemented
                    │
                    ▼
   Structural Graph JSON + Diagnostics   ← implemented
                    │
                    ▼
      Service Grouping Artifact          ← implemented optional overlay
                    │
                    ▼
         Service Graph Artifact          ← implemented optional overlay
                    │
                    ▼
         Attack Transition Derivation    ← later phase
                    │
                    ▼
      LLM File + Attack Edge Scoring     ← later phase
                    │
                    ▼
            Weighted Attack Graph        ← later phase
                    │
                    ▼
         Deterministic Attack Search     ← later phase
                    │
                    ▼
      Recommendation Report Artifact    ← implemented once path input exists
```

Core idea:

* files are the unit of reasoning
* the file graph remains the authoritative extraction/search foundation
* service grouping is a derived overlay, not a replacement for the canonical file graph
* files can act as entry, transition, or target nodes by role rather than by node type
* structural dependencies define what is possible
* attack-transition edges define how attackers plausibly move
* one LLM call per file assigns target-ness and node risk
* one LLM call per structural edge assigns attack-transition semantics and traversal cost
* target risk belongs on end nodes, while traversal cost belongs on edges
* graph search computes likely paths once weights are assigned
* explanations are grounded in real files and real dependencies

---

# Why This Scope Reduction Is Good

The earlier service-level approach introduced major complexity:

* service-boundary inference
* service-to-file assignment
* validation of semantic architecture
* more ambiguous graph abstractions

The file-level MVP removes those problems.

Benefits:

* every node is real and visible
* graph construction is easier to validate
* attack paths are easier to trace back to evidence
* the team can focus on one strong capability: **attack path prediction over code**

---

# Core Components

## 1. File Graph Extraction

The system converts a repository into a directed graph of files and their relationships.

### Current implementation notes

The current implementation uses CodeGraph as the extraction backbone and then performs a Pathfinder-owned projection layer on top of it.

Current emitted structural relationship types are derived from CodeGraph relations such as:

* `imports`
* `imports_symbol`
* `reexports`
* `uses_symbol`
* `extends`
* `implements`

These are collapsed into Pathfinder structural edges such as:

* `imports`
* `calls`
* `references`

The extractor also:

* drops self-edges
* tracks omitted relations in diagnostics
* preserves provenance per structural edge
* emits summary counts that reconcile with the serialized artifact

### Node type

* source file

### Edge types

* imports
* calls into
* references
* includes
* uses shared utility

In practice, the initial graph is currently derived from CodeGraph and then collapsed to **file-to-file structural edges**.

### Output

A structural file graph such as:

```text
auth_handler.py → session_manager.py
session_manager.py → permissions_store.py
permissions_store.py → db_client.py
```

This graph is the structural foundation of Pathfinder.

It does **not** yet say how attackers move. It only says which file relationships exist in code.

The current structural artifact also includes:

* `summary`
* `diagnostics`
* empty `attack_edges`

This keeps the persisted output aligned with later phases while remaining structurally grounded today.

---

## 2. Attack Transition Derivation

The system derives an **attack graph** from the structural file graph.

This layer is **not implemented yet**. It remains the next major architecture step after the structural graph foundation.

In this graph:

* nodes are still files
* files may serve as entry files, intermediate transition files, or target files
* edges represent plausible attacker transitions
* edges are labeled with attack mechanisms where possible

Examples:

```text
api/login.js --(SQL Injection)--> db/db.js
api/auth.js --(Broken Authentication)--> api/admin.js
api/user.js --(IDOR)--> api/profile.js
```

This is a key design improvement: attack paths should run over **attack transitions**, not over generic imports alone.

`target` is a file role, not a separate node type. A file can be a transition node in one path and a target node in another.

---

## 3. MVP Input Surface

For the first version, the only required input is the repository itself.

Pathfinder should infer likely attacker movement from:

* file structure
* dependency relationships
* entrypoint-like exposure signals
* target-like payoff signals
* security-relevant code semantics

This keeps the MVP focused on one core capability:

> infer the most likely attacker path through the codebase without requiring scenario setup.

Attack goals, explicit starting files, vulnerability inputs, and analyst hints can be added later once the baseline pathing works reliably.

---

## 4. LLM File and Edge Analysis Engine

This component assigns structured node-level value to files and structured traversal cost to attack transitions.

This entire section describes the intended later-phase architecture. It is not yet implemented in the repository.

### Bounded call pattern

* **one LLM call per file**
* **one LLM call per structural edge**

### Inputs per file

* file path
* file content or summary
* local dependency neighborhood
* exposure and boundary hints inferred from code structure

### Outputs per file

* `target_flag`
* `normalized_risk_score`
* confidence
* short rationale
* optional supporting sub-scores

These outputs define whether the file is a likely attacker destination and how valuable it is if reached.

### Outputs per structural edge

* whether a plausible `attack_transition` exists
* attack type
* `edge_attack_cost`
* transition likelihood
* required capability
* detection risk
* confidence
* short rationale

If the structural edge does not support a plausible attacker move, Pathfinder should emit no attack edge for that relationship. If it does, the emitted `attack_transition` carries the traversal cost used by search.

For the MVP, this scoring is **goal-agnostic**.

The model estimates general attacker usefulness and movement feasibility first. Goal-conditioned scoring can be added later once the base system is working well.

### Why the LLM is useful here

The LLM can reason over semantics that are hard to encode with simple rules, for example:

* authentication logic
* admin controls
* database access
* trust boundaries
* privilege-sensitive code paths

It can also distinguish between very different attacker transitions, such as:

* SQL injection into database access
* broken authentication into admin-only routes
* IDOR into profile or object data access

---

## 5. Edge Model

### Do edges need weights?

**Yes — in the attack graph, they should.**

The system should distinguish between:

* **structural edges** from code relationships
* **attack edges** from plausible attacker movement

Structural edges are evidence. Attack edges are the edges used for attack-path search.

### Recommended MVP approach

Use structural relationships to generate candidate transitions, then run one bounded LLM analysis per structural edge to decide whether to materialize an attack edge and what traversal cost it should carry.

Example:

* `api/login.js --(SQL Injection)--> db/db.js`
* `api/auth.js --(Broken Authentication)--> api/admin.js`
* `api/user.js --(IDOR)--> api/profile.js`

Node risk represents **attacker payoff at the destination**. Edge weights represent **attacker movement feasibility during traversal**.

### Why derive attack edges from structure first?

Using structure first:

* keeps the graph grounded in real code relationships
* limits the number of candidate transitions to score
* makes explanations easier to justify
* avoids scoring arbitrary file pairs

So the recommended design is:

> **structural graph for grounding, LLM-scored attack edges for movement, LLM-scored nodes for value.**

---

## 6. Weighted Attack Graph

The weighted attack graph is built from:

* file nodes with role flags
* attack-transition edges
* node target-value scores
* edge movement costs

Traversal should be computed on edges, while node risk remains attached to the destination file.

One practical decomposition is:

```text
path_traversal_cost(P)
= Σ(edge_attack_cost(e) + hop_penalty)

path_target_value(P)
= normalized_risk_score(last_node(P))
```

Interpretation:

* higher-value target files are more attractive attacker destinations
* harder attack transitions are more expensive to traverse
* long paths still incur cost via hop penalties

Search should begin from entry-like files and terminate at `target_flag` files. Ranking can combine low traversal cost with high target value, but node risk should not be folded into per-edge traversal cost.

---

## 7. Deterministic Attack Path Search

Once weights are assigned, path search should be deterministic.

Useful algorithms for MVP:

* Dijkstra for lowest-cost path
* Yen's algorithm for top-k shortest paths
* simple bounded-depth search for demo scenarios

### Outputs

* best inferred path from an entry-like file to a target-flagged file
* top-k alternative paths
* highest-risk intermediate files
* files that frequently appear across strong paths

These repeated files become natural mitigation choke points.

---

## 8. Explanation Layer

For each predicted path, Pathfinder should explain:

* why the inferred starting file matters
* why each intermediate file is attractive to an attacker
* why the final file is valuable or security-sensitive
* what file should be reviewed or patched first

This explanation can be generated by an LLM, but it must reference:

* real files
* real structural evidence
* real attack edges
* real scores

The repository now includes this layer as a standalone post-path phase boundary:

* `RecommendationReportInputArtifact` supplies ordered path nodes, ordered path edges, and focal files
* `RecommendationReportArtifact` persists mitigation priorities, path narrative, citations, diagnostics, and LLM audit metadata
* prompt/template versioning and rendered prompt bodies are recorded for observability
* the report layer is intentionally separate from the graph schema so structural, attack, search, and reporting artifacts stay distinct

---

## Derived service overlay

The repository now also includes a separate service overlay boundary:

* `ServiceGroupingArtifact` stores LLM-proposed service groups resolved into grounded file assignments
* `ServiceGraphArtifact` stores deterministic service-to-service edges aggregated from structural file edges
* file nodes and structural edges remain canonical; the service layer is a projection on top
* service edges may only be emitted when supported by existing structural edges

---

# Data Model

## File Node Schema

Example fields:

```text
file_path
language
entrypoint_flag
target_flag
import_count
out_degree
in_degree
security_scores
normalized_risk_score
confidence
rationale
```

## Edge Schema

Example fields:

```text
source_file
target_file
structural_basis
attack_type
transition_likelihood
edge_attack_cost
confidence
excluded_flag
```

---

# Workflow

## Step 1: Parse Repository

Extract files and their dependency relationships.

## Step 2: Build File Graph

Construct a structural graph where files are nodes.

## Step 3: Run Per-File LLM Analysis

For each file, assign `target_flag`, `normalized_risk_score`, confidence, and rationale.

## Step 4: Run Per-Structural-Edge LLM Analysis

For each structural edge, decide whether it supports a plausible attacker move and, if so, emit an attack edge with `edge_attack_cost`.

## Step 5: Build Weighted Graph

Assemble file roles and target scores on nodes, and traversal cost on attack edges.

## Step 6: Run Path Search

Compute most likely attack paths from entry-like files to target-flagged files.

## Step 7: Explain and Prioritize

Return the path, key files, and recommended mitigation focus.

## Step 8: Persist Recommendation Report Artifact

Serialize the grounded recommendation report, including prompt/model audit data, for review and downstream tooling.

---

# Architecture Quality Goals

## Feasibility

The MVP should work on a bounded repository without requiring service inference, runtime telemetry, or infrastructure modeling.

## Explainability

Every predicted path must be traceable to real files, real structural dependencies, and real attack-transition evidence.

## Cost Efficiency

LLM usage should be bounded to one pass per file and one pass per structural edge, not used during path search itself.

## Determinism After Scoring

Once file target flags, node risk, and edge traversal costs are assigned, path computation should be deterministic and repeatable.

## Extensibility

The file-level model should later support:

* service-level abstractions
* richer edge models
* vulnerability ingestion
* runtime context

---

# Responsible AI Guardrails

Pathfinder should use AI in a controlled way.

Guardrails:

* the LLM scores files, but does not invent files or dependencies
* graph structure must come from extracted code relationships
* attack edges must be justified by structural evidence and attack rationale
* the LLM may only materialize attack edges for existing structural edges
* outputs should be schema-constrained and numeric where possible
* explanations must refer to real files and path evidence
* high-impact mitigation decisions remain reviewable by humans

---

# Example

## Example Path

One plausible output for a repository might be:

## Graph

```text
auth_handler.py --(session abuse)--> session_manager.py --(broken authorization)--> admin_access.py --(privilege propagation)--> permissions_store.py
```

## File scores

```text
auth_handler.py: 0.82
session_manager.py: 0.71
admin_access.py: 0.93
permissions_store.py: 0.88
```

## Interpretation

The graph search favors this path because it moves from an exposed identity-handling file into session logic, then into privilege-sensitive authorization code, and finally into a high-value permissions store.

---

# Future Architecture Evolution

Once the file-level MVP works well, Pathfinder can evolve toward:

* attack-goal conditioning
* explicit entry-file or vulnerability input
* clustered file groups
* service-level overlays
* runtime telemetry
* richer transition models
* CVE-to-file mapping
* attack copilot interfaces

But the file graph MVP should come first.

---

# Summary

The MVP should answer:

> **Given a codebase, what is the most likely path an attacker would take through the code?**

Pathfinder's MVP architecture should be:

> **structural file graph extraction + one LLM pass per file for target/risk + one LLM pass per structural edge for attack edges/cost + deterministic path search**

That is a strong, realistic, and defensible first version.

On the edge-weight question specifically:

> **Yes — attack edges should carry security meaning and weights.**

The important distinction is that these are not generic dependency edges. They are derived **attack-transition edges** such as SQL injection, broken authentication, or IDOR, grounded in structural file relationships, and they carry traversal cost while target-node risk stays on the destination file.