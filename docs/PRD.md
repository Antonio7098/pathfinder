# Product Requirements Document (PRD)

## Pathfinder – File-Level AI Attack Path Prediction

---

# 1. Product Overview

**Product Name:** Pathfinder
**Category:** AI-Accelerated Cyber Defense / Attack Path Prediction
**Tagline:** *AI that reduces cyber threat analysis from hours to seconds.*

**Primary Goal:** Reduce **Mean Time To Respond (MTTR)** by helping analysts answer one urgent question quickly:

> If an attacker starts here, what is the most likely path through this codebase?

Pathfinder's MVP deliberately reduces scope.

Instead of inferring services, environments, and runtime topology, Pathfinder starts with a simpler and more buildable model:

* each **file** is a graph node
* file dependencies create the **structural graph**
* plausible attacker moves become **attack-transition edges**
* an LLM assigns attack-relevant **risk weights** to files and transitions
* a graph algorithm calculates the most likely attack path

This keeps the system grounded, demoable, and technically credible for an MVP.

---

# 2. Problem Statement

When a vulnerability appears, security teams often need to:

1. locate the affected code
2. understand what that code touches
3. trace dependencies manually
4. reason about attacker movement
5. decide what to patch or monitor first

This is slow, especially in unfamiliar or large codebases.

Existing tools often produce:

* long lists of vulnerable files or packages
* weak prioritization
* little context on likely attack progression
* no clear “fix this first” story

Pathfinder addresses this by turning the codebase into a structural file graph, deriving an attack graph from that structure, and ranking likely attack paths automatically.

---

# 3. Product Vision

Pathfinder is an AI-assisted code risk engine that combines:

* **file-level graph extraction from code**
* **LLM-based file and attack-transition scoring**
* **deterministic graph search**

High-level workflow:

```text
Vulnerability or attack goal appears
        ↓
Pathfinder builds a structural file graph
        ↓
Pathfinder derives attack-transition edges
        ↓
LLM scores files and transitions for attack relevance
        ↓
Graph engine computes likely attack paths
        ↓
Pathfinder surfaces the top path and key files
```

The result is a practical MVP that can show clear value without needing full service inference or runtime telemetry.

### Why This Reduced Scope Makes Sense

This version is smaller, faster to build, and easier to validate because:

* files are explicit and directly observable
* file dependencies are easier to extract than service boundaries
* file-level scoring is easier to explain in a demo
* attack paths can still be computed meaningfully from code structure

---

# 4. Target Users

### Primary Users

* SOC analysts
* application security engineers
* security architects

### User Outcomes

Users should be able to:

* identify the most dangerous code path quickly
* understand which files are likely stepping stones for an attacker
* prioritize patching, review, or monitoring actions
* explain why a predicted path matters

---

# 5. Core Product Capabilities

### File Graph Construction

Pathfinder builds a graph where:

* **nodes** = source files
* **structural edges** = dependency or reference relationships between files

Example file nodes:

* `auth.py`
* `billing_service.py`
* `db_client.py`
* `admin_routes.py`

This graph is the structural substrate, not yet the full attack model.

---

### Attack Transition Derivation

Pathfinder derives an attack graph from the structural file graph.

In the attack graph:

* **nodes** remain files
* **edges** represent plausible attacker moves between files
* edges are labeled with attack mechanisms where possible

Example attack edges:

* `api/login.js --(SQL Injection)--> db/db.js`
* `api/auth.js --(Broken Authentication)--> api/admin.js`
* `api/user.js --(IDOR)--> api/profile.js`

This makes the graph cyber-specific rather than just dependency-aware.

---

### LLM File Risk Scoring

For each file, the LLM assigns structured scores related to one or more attack goals.

Example attack goals:

* data exfiltration
* privilege escalation
* ransomware
* persistence

Example scoring factors:

* exploitability
* privilege gain potential
* sensitivity of accessed data
* lateral movement value
* detectability

Files represent the **value** or **usefulness** of compromise.

---

### Attack Edge Scoring

For each plausible attack transition, Pathfinder assigns structured scores such as:

* attack type
* transition likelihood
* required attacker capability
* confidence
* detection risk

Attack edges represent the **feasibility of movement** between files.

---

### Attack Path Prediction

Using the weighted attack graph, Pathfinder computes:

* most likely attack path
* top-k likely attack paths
* highest-risk intermediate files
* likely choke points for mitigation

---

### Explainable Output

For the top predicted path, Pathfinder explains:

* why each file matters
* what attack goal the path supports
* which files should be patched, reviewed, or monitored first

---

# 6. Core Concepts

## File Node

A file in the codebase represented as a graph node.

## Dependency Edge

A directed structural relationship showing one file depends on, imports, references, or calls into another.

## Attack Transition Edge

A directed attack-oriented relationship showing how compromise or abuse of one file could enable movement into another.

Examples include:

* SQL injection
* broken authentication
* insecure direct object reference
* privilege escalation
* unsafe database access

## File Risk Weight

A numeric score assigned by the LLM indicating how valuable or useful a file is to an attacker for a specific attack goal.

## Attack Edge Weight

A numeric score assigned to an attack transition indicating how plausible, easy, or effective that movement is for an attacker.

## Attack Path

A sequence of connected files that represents likely attacker progression.

---

# 7. Product Decisions For MVP

## Node Weights: Yes

Node weights are core to the MVP.

Each file should receive LLM-generated risk values.

## Edge Weights: Yes, In The Attack Graph

Edges in the **attack graph** should represent attack risk, not just generic dependencies.

Recommended MVP approach:

* use structural dependencies to generate candidate transitions
* score **files** for attacker value
* score **attack edges** for movement feasibility

This keeps the system grounded while making the graph meaningfully security-specific.

Structural relation types still matter, but mainly as evidence or priors for whether an attack edge is possible.

---

# 8. System Requirements

### Inputs

* source code repository
* optional vulnerability or entry-file input
* selected attack goal

### Outputs

* structural file graph
* weighted attack graph
* top predicted attack path
* top-k alternative paths
* key risky files
* mitigation suggestions

### Non-Functional Requirements

* grounded in real files and dependencies
* bounded LLM usage
* deterministic path calculation after scoring
* explainable output suitable for demo and analyst review

---

# 9. Risk Scoring Model

For each file, Pathfinder asks the LLM to produce structured numeric outputs such as:

```text
exploitability
privilege_gain
data_access_value
lateral_movement_value
detection_risk
confidence
```

These are combined into a file-level risk score for a chosen attack goal.

For each candidate attack edge, Pathfinder also produces structured outputs such as:

```text
attack_type
transition_likelihood
required_capability
detection_risk
confidence
```

For MVP, node scores represent **attacker payoff**, while edge scores represent **attacker movement feasibility**.

Suggested path-cost idea:

```text
transition_cost(u → v)
= edge_attack_cost(u, v)
+ hop_penalty
+ (1 - normalized_risk_score(v))
```

Lower-cost paths are treated as more likely attacker paths.

---

# 10. Core Workflow

### Step 1: Ingest Codebase

Build a structural file graph from the repository.

### Step 2: Select Scenario

Choose an attack goal and, if known, an entry file or vulnerable file.

### Step 3: Derive Attack Transitions

Use structural relationships plus vulnerability patterns to derive plausible attack edges.

### Step 4: Score Files and Attack Edges

Use the LLM to assign attack-relevant risk weights to files and attack transitions.

### Step 5: Run Path Search

Use a graph algorithm to compute the most likely attack path and top alternatives.

### Step 6: Explain Results

Generate a human-readable explanation and mitigation priorities.

---

# 11. MVP Scope

The hackathon MVP will include:

### File Graph Extraction

Build a graph from repository files and their dependencies.

### Attack Edge Derivation

Derive plausible attack transitions from structurally connected files.

### LLM File Scoring

Score each file for at least 3 attack goals.

### LLM Attack Edge Scoring

Score candidate attack transitions with attack-type labels and likelihood values.

### Path Search

Compute the top 3 likely attack paths from a chosen starting point.

### Explanation Layer

Explain why the path was selected and what the key risky files are.

### Lightweight Visualization

Show a graph or path output that is understandable in a short demo.

---

# 12. Success Metrics

### MTTR Reduction

Measure time required to move from “vulnerability or attack goal identified” to “top likely path and first mitigation suggestion shown.”

### Path Quality

Validate whether top predicted paths look plausible to a technical reviewer.

### Explainability

Ensure each predicted path can be explained in terms of real files, real structural dependencies, real attack transitions, and real scoring rationale.

### MVP Feasibility

The system should work on a bounded demo repository without requiring runtime telemetry or service discovery.

---

# 13. Example Scenario

Input:

```text
Attack goal: privilege escalation
Entry file: auth_handler.py
```

Predicted path:

```text
auth_handler.py
--(session abuse)--> session_manager.py
--(broken authorization)--> admin_access.py
--(privilege propagation)--> permissions_store.py
```

Why this path ranks highly:

* `auth_handler.py` is exposed and likely attacker-reachable
* `session_manager.py` handles trust and identity state
* `admin_access.py` represents privilege escalation value
* `permissions_store.py` is a high-value authorization target
* the attack edges describe plausible attacker movement, not just file imports

Suggested mitigation:

* review and harden `auth_handler.py`
* inspect privilege checks in `admin_access.py`
* add monitoring around authorization-sensitive paths

---

# 14. Future Enhancements

Potential future extensions after the file-level MVP:

* service-level graph abstraction
* runtime telemetry enrichment
* richer edge weighting
* vulnerability-to-file auto-mapping
* attack-profile libraries
* analyst copilot interface

---

# 15. Summary

Pathfinder's reduced-scope MVP focuses on one strong and buildable capability:

> Build a structural file graph, derive attack-transition edges, score files and transitions for attacker usefulness, and calculate the most likely path of attack through the codebase.

More precisely, Pathfinder:

> builds a structural file graph, derives attack-transition edges between files, scores nodes and edges for attacker utility, and ranks the most likely attack path through the application.

This is a much tighter and more achievable first version than full service inference, while still clearly demonstrating how AI can accelerate cyber threat analysis.