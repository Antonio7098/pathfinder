# Pathfinder Architecture

## Overview

Pathfinder's MVP uses a **file-level attack graph**.

This is a deliberate scope reduction from service-level architecture inference.

The system answers a simpler and more achievable question:

> Given a codebase, what is the most likely path an attacker would take through the code?

The architecture combines:

* **file graph extraction from source code**
* **attack-transition derivation from structural relationships**
* **LLM-based file and attack-edge scoring**
* **deterministic path search**

This is the right MVP shape because it is:

* grounded in explicit code artifacts
* smaller and faster to implement
* easier to explain and demo
* extensible toward richer future models

---

# High-Level Architecture

```text
Codebase
                    │
                    ▼
           File Graph Extraction
                    │
                    ▼
          Structural File Graph
                    │
                    ▼
         Attack Transition Derivation
                    │
                    ▼
      LLM File + Attack Edge Scoring
                    │
                    ▼
            Weighted Attack Graph
                    │
                    ▼
         Deterministic Attack Path Search
                    │
                    ▼
      Top Path / Top-K Paths / Explanations
```

Core idea:

* files are the unit of reasoning
* structural dependencies define what is possible
* attack-transition edges define how attackers plausibly move
* the LLM scores file value and transition feasibility
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

### Node type

* source file

### Edge types

* imports
* calls into
* references
* includes
* uses shared utility

In practice, the initial graph can be derived from CodeGraph or another code indexing layer, then collapsed to **file-to-file structural edges**.

### Output

A structural file graph such as:

```text
auth_handler.py → session_manager.py
session_manager.py → permissions_store.py
permissions_store.py → db_client.py
```

This graph is the structural foundation of Pathfinder.

It does **not** yet say how attackers move. It only says which file relationships exist in code.

---

## 2. Attack Transition Derivation

The system derives an **attack graph** from the structural file graph.

In this graph:

* nodes are still files
* edges represent plausible attacker transitions
* edges are labeled with attack mechanisms where possible

Examples:

```text
api/login.js --(SQL Injection)--> db/db.js
api/auth.js --(Broken Authentication)--> api/admin.js
api/user.js --(IDOR)--> api/profile.js
```

This is a key design improvement: attack paths should run over **attack transitions**, not over generic imports alone.

---

## 3. MVP Input Surface

For the first version, the only required input is the repository itself.

Pathfinder should infer likely attacker movement from:

* file structure
* dependency relationships
* entrypoint-like exposure signals
* security-relevant code semantics

This keeps the MVP focused on one core capability:

> infer the most likely attacker path through the codebase without requiring scenario setup.

Attack goals, explicit starting files, vulnerability inputs, and analyst hints can be added later once the baseline pathing works reliably.

---

## 4. LLM File and Attack Scoring Engine

This component assigns structured risk scores to files and attack transitions.

### Inputs per file

* file path
* file content or summary
* local dependency neighborhood
* exposure and boundary hints inferred from code structure

### Outputs per file

* exploitability
* privilege gain potential
* sensitive data access value
* lateral movement value
* detection risk
* confidence
* short rationale

These outputs are normalized into a file-level risk score.

### Outputs per attack edge

* attack type
* transition likelihood
* required capability
* detection risk
* confidence
* short rationale

These outputs are normalized into attack-transition costs or likelihoods.

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

Use structural relationships to generate candidate transitions, then score those transitions as attack edges.

Example:

* `api/login.js --(SQL Injection)--> db/db.js`
* `api/auth.js --(Broken Authentication)--> api/admin.js`
* `api/user.js --(IDOR)--> api/profile.js`

Node weights represent **attacker payoff**. Edge weights represent **attacker movement feasibility**.

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

* file nodes
* attack-transition edges
* node value scores
* edge movement scores

One practical formulation is to treat the cost of moving into a file as:

```text
transition_cost(u → v)
= edge_attack_cost(u, v)
+ hop_penalty
+ (1 - normalized_risk_score(v))
```

Interpretation:

* higher-value files are cheaper for the attacker to reach
* harder attack transitions are more expensive
* long paths still incur cost via hop penalties

This makes standard shortest-path methods useful.

---

## 7. Deterministic Attack Path Search

Once weights are assigned, path search should be deterministic.

Useful algorithms for MVP:

* Dijkstra for lowest-cost path
* Yen's algorithm for top-k shortest paths
* simple bounded-depth search for demo scenarios

### Outputs

* best inferred path from an entry-like file to a high-value target region
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

---

# Data Model

## File Node Schema

Example fields:

```text
file_path
language
entrypoint_flag
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

## Step 3: Derive Attack Transitions

Use structural relationships and security-relevant code patterns to derive plausible attack edges.

## Step 4: Score Files and Attack Edges

Run LLM-based scoring over files and derived attack transitions using local context and inferred attacker relevance.

## Step 5: Build Weighted Graph

Assign node value scores and edge attack costs.

## Step 6: Run Path Search

Compute most likely attack path and alternatives.

## Step 7: Explain and Prioritize

Return the path, key files, and recommended mitigation focus.

---

# Architecture Quality Goals

## Feasibility

The MVP should work on a bounded repository without requiring service inference, runtime telemetry, or infrastructure modeling.

## Explainability

Every predicted path must be traceable to real files, real structural dependencies, and real attack-transition evidence.

## Cost Efficiency

LLM usage should be concentrated in file scoring, not in every graph operation.

## Determinism After Scoring

Once file weights are assigned, path computation should be deterministic and repeatable.

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

> **structural file graph extraction + attack-transition derivation + LLM node and edge scoring + deterministic path search**

That is a strong, realistic, and defensible first version.

On the edge-weight question specifically:

> **Yes — attack edges should carry security meaning and weights.**

The important distinction is that these are not generic dependency edges. They are derived **attack-transition edges** such as SQL injection, broken authentication, or IDOR, grounded in structural file relationships.