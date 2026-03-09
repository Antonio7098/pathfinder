# Pathfinder Architecture

## Overview

Pathfinder is an **AI-accelerated cyber defense system** designed to reduce **Mean Time To Respond (MTTR)** by compressing three expensive parts of cyber analysis:

* **threat discovery time**
* **attack path analysis time**
* **mitigation decision time**

It does this by combining:

* **Code-derived architecture graphs**
* **Deterministic graph algorithms**
* **LLM semantic enrichment**

The system automatically derives a **service-level architecture graph** from a codebase using the CodeGraph knowledge graph, maps vulnerabilities to affected services, then simulates attacker movement across that architecture using a weighted attack graph model.

The goal is to answer questions such as:

* *If an attacker exploits vulnerability X, what is the most likely path to sensitive assets?*
* *Which architectural nodes are critical choke points?*
* *Which services represent the highest security risk?*
* *Which node should we patch, monitor, or segment first?*

The architecture emphasizes **deterministic structural reasoning** with **LLMs used for interpretation and enrichment rather than core graph computation**.

The key product story is not simply that Pathfinder "uses an LLM." The architecture is designed so that AI **dramatically reduces the time required to understand and respond to threats**.

---

# High-Level Architecture

```
Codebase                         Vulnerability / CVE Input
   │                                      │
   ▼                                      ▼
CodeGraph Extraction          LLM Vulnerability Interpretation
   │                                      │
   ▼                                      │
Service Discovery Engine                  │
   │                                      │
   ▼                                      │
Service Graph Construction                │
   │                                      │
   └──────────────► Attack Graph Engine ◄─┘
                          │
                          ▼
             LLM Enrichment + Security Copilot
                          │
                          ▼
  Security Insights / Dashboard / Mitigation Recommendations
```

Core idea:

* **CodeGraph provides structural truth**
* **Graph algorithms produce deterministic architecture and attack paths**
* **LLMs provide semantic understanding, explanations, and mitigation guidance**
* **The full pipeline is optimized to reduce MTTR from hours to seconds on bounded scenarios**

---

# MTTR Reduction Model

Pathfinder is intentionally designed to remove the main human bottlenecks in cyber response.

## 1. Threat Discovery Time

Pathfinder reduces discovery time by:

* deriving architecture directly from code
* surfacing affected services automatically
* converting natural-language advisories into structured signals

## 2. Attack Path Analysis Time

Pathfinder reduces analysis time by:

* constructing a service graph automatically
* simulating likely attacker movement over an attack graph
* identifying choke points and crown-jewel exposure immediately

## 3. Mitigation Decision Time

Pathfinder reduces decision time by:

* explaining why a path is risky
* grounding recommendations in graph structure
* allowing analysts to ask targeted questions through a security copilot

What is normally a manual workflow — reading advisories, searching the codebase, tracing dependencies, understanding architecture, and proposing mitigations — is compressed into a single automated pipeline.

---

# Core Components

## 1. CodeGraph Extraction

The system begins by converting a codebase into a structured **CodeGraph**.

CodeGraph represents:

Nodes:

* repository
* directory
* file
* symbol

Edges:

* contains
* defines
* uses_symbol
* imports_symbol
* exports
* implements / extends

This graph captures the **true dependency structure of the codebase**.

Example:

```
symbol:login_handler
   └─uses_symbol→ validate_token
        └─uses_symbol→ get_user_by_id
```

The CodeGraph is the **source of truth** for all architectural inference.

---

# 2. Service Discovery Engine

The Service Discovery Engine extracts **candidate architectural units** from the CodeGraph.

These are potential **service nodes** such as:

* authentication service
* billing service
* notification worker
* admin interface
* agent runtime

Because real architectures are rarely explicit in code, Pathfinder uses **deterministic heuristics** to infer these units.

This is one of the first major MTTR gains: analysts no longer need to manually reverse-engineer architecture before reasoning about security impact.

---

## Candidate Generation

Candidate nodes are generated from structural boundaries such as:

* top-level directories
* directories under `apps/`
* directories under `services/`
* directories under `workers/`
* directories under `packages/`
* directories containing exported/public symbols

Each candidate represents a **subtree of the codebase**.

Example:

```
services/auth
services/billing
workers/email
packages/db
```

---

## Candidate Feature Extraction

For each candidate subtree the system computes structural metrics.

Examples include:

### Size

```
file_count
symbol_count
```

Tiny clusters are unlikely to represent services.

---

### Public Surface

```
exported_symbol_count
entrypoint_symbol_count
```

Services typically expose entrypoints such as:

* handlers
* controllers
* API endpoints
* background job triggers

---

### Internal Cohesion

Measures how strongly files within the subtree depend on each other.

High cohesion indicates a coherent subsystem.

---

### External Coupling

Measures how often the subtree references external symbols.

Too much coupling may indicate the candidate is not a true boundary.

---

### Dependency Direction

```
inbound_dependencies
outbound_dependencies
```

A shared library often has many inbound dependencies but few outbound ones.

---

### Semantic Signals

Simple deterministic keyword signals from:

* directory names
* file names
* symbol names

Examples:

```
auth
billing
payment
admin
notification
agent
worker
```

These help identify domain boundaries.

---

# Candidate Scoring

Candidates are scored according to **service-likeness**.

Example conceptual scoring:

```
service_score =
  cohesion_score
+ public_surface_score
+ semantic_score
+ size_score
- utility_penalty
- overfragmentation_penalty
```

Candidates that score above a threshold become **service nodes**.

---

# Node Promotion

Because candidates often overlap, Pathfinder promotes nodes using deterministic rules:

1. Prefer **more specific subtrees** over broad parents.
2. Avoid promoting both parent and child nodes unless clearly distinct.
3. Ensure each file belongs to **exactly one promoted node**.

Example:

```
services/
services/auth/
services/auth/tokens/
```

Promoted node:

```
services/auth
```

All descendant files and symbols become members of that service node.

---

# 3. Service Graph Construction

Once service nodes are identified, Pathfinder constructs a **Service Graph**.

Nodes represent:

```
Authentication Service
Billing Service
Notification Worker
Database Access Layer
```

Edges represent **cross-service dependencies**.

---

## Edge Extraction

Edges are derived from CodeGraph symbol dependencies.

Procedure:

1. For each `uses_symbol` edge:

   * determine source symbol's service
   * determine target symbol's service

2. If services differ:

```
source_service → target_service
```

3. Increment dependency weight.

Example:

```
web_service → auth_service
auth_service → database_layer
billing_service → notification_worker
```

Edges capture **logical service dependencies**.

---

# 4. Attack Graph Engine

The Service Graph becomes the basis of the **Attack Graph**.

Because the graph is derived from code structure, Pathfinder can begin impact analysis immediately once a vulnerability is mapped to a service.

Attack Graph nodes represent:

* services
* entrypoints
* critical assets

Edges represent **possible attacker movement**.

Example:

```
Internet
   ↓
Web Service
   ↓
Auth Service
   ↓
Admin Console
   ↓
Database
```

---

## Graph Engine

The attack graph is implemented using **NetworkX**.

NetworkX provides algorithms for:

* shortest paths
* weighted traversal
* centrality detection
* choke-point discovery

---

## Risk Scoring

Edges are weighted using a deterministic risk model.

Example factors:

```
exploitability
+ reachability
+ privilege_gain
+ goal_alignment
+ downstream_potential
- detection_risk
- segmentation_penalty
```

This produces a **cost score** for attacker movement.

Graph traversal then identifies:

* most probable attack paths
* alternative paths
* choke points

---

# 5. Attacker Intent Model

Attack simulation is conditioned on **attacker goals**.

Examples:

```
data_exfiltration
ransomware
financial_fraud
persistence
system_sabotage
```

Each goal modifies risk weights.

Example:

Data exfiltration prioritizes:

```
database
data_export APIs
reporting systems
```

Ransomware prioritizes:

```
identity systems
orchestration services
backup systems
fleet control
```

This produces **goal-specific attack paths**.

---

# 6. LLM Enrichment Layer

LLMs are used for **semantic understanding**, not structural reasoning.

The deterministic graph engine produces architecture and attack paths.

The LLM layer enriches this with interpretation.

---

## Service Labeling

The LLM analyzes service clusters and generates human-readable labels.

Example input:

```
Directory: services/auth
Exported symbols:
login_handler
validate_token
refresh_session
```

Output:

```
Authentication Service
Responsibilities:
- login
- token validation
- session management
```

---

## Capability Detection

LLMs classify services by capability:

Examples:

```
authentication
payment processing
database access
file system access
agent orchestration
```

This provides **security context**.

---

## Vulnerability Interpretation

Threat feeds or CVE descriptions can be translated into structured signals.

Example:

```
CVE description
→ exploit_type
→ privilege impact
→ affected components
```

These signals adjust graph weights.

This is where AI directly removes a major human bottleneck: natural-language vulnerability reports become machine-usable security signals in seconds.

---

## Attack Path Explanation

LLMs convert graph results into human-readable explanations.

Example:

> The web service exposes an endpoint that calls the authentication service. The authentication service contains a vulnerability that allows privilege escalation, enabling access to the admin console and ultimately the user database.

---

## Mitigation Suggestions

LLMs generate defensive recommendations:

* patch vulnerabilities
* add segmentation
* add monitoring
* restrict permissions

These recommendations are grounded in graph outputs, which helps reduce **mitigation decision time** without sacrificing explainability.

---

# 7. Security Copilot Interface

A grounded analyst interface sits on top of the graph stack.

Example queries:

```text
Which services could lead to database compromise?
What is the most likely ransomware path?
Which node should we patch first?
```

The copilot does not invent topology. It answers by retrieving evidence from the CodeGraph, Service Graph, and Attack Graph, then uses the LLM to produce concise analyst-facing responses.

---

# 8. Security Insights

Pathfinder produces several outputs.

## Instant Vulnerability Impact Analysis

Example input:

```text
CVE-XXXX affects Auth Service
```

Example output:

```text
Internet → Web Service → Auth Service → Billing Service → Payment DB
Patch Auth Service first; add monitoring on Billing API
```

This is the most visible demonstration of Pathfinder's speed advantage.

---

## Attack Path Prediction

Example:

```
Internet
→ Web Service
→ Auth Service
→ Database
```

---

## Choke Point Detection

Nodes appearing across many paths are highlighted as defensive priorities.

---

## Service Risk Profiles

Each service receives a risk profile including:

* attack surface
* dependency fan-out
* sensitive capability exposure

---

# Data Model

## Service Node

Example structure:

```
{
  id: "service_auth",
  root_directory: "services/auth",
  file_count: 18,
  symbol_count: 74,
  exported_symbols: 12,
  capabilities: ["authentication", "session_management"],
  risk_score: 0.78
}
```

---

## Service Edge

```
{
  source: "web_service",
  target: "auth_service",
  dependency_count: 23,
  risk_weight: 0.42
}
```

---

# Design Principles

## MTTR First

Every layer in Pathfinder should shorten one of three delays:

* code and architecture comprehension
* attack path reasoning
* mitigation planning

---

## Deterministic Structure

Architecture discovery is based on graph analysis and heuristics rather than LLM inference.

---

## Explainability

Every node and edge can be traced back to:

* source files
* symbol dependencies
* deterministic scoring rules

---

## Layered Graph Model

Pathfinder operates across multiple graph layers:

```
CodeGraph → Service Graph → Attack Graph
```

---

## Hybrid AI + Deterministic Reasoning

LLMs enhance interpretation but never replace deterministic reasoning.

This hybrid model is what gives Pathfinder:

* fast analysis
* consistent results
* explainable decisions

---

# Future Extensions

Possible future capabilities include:

### Code-Level Attack Paths

Expanding service nodes into symbol-level attack chains.

---

### Automatic Architecture Discovery

Using dependency community detection to identify architectural clusters in messy monoliths.

---

### Runtime Integration

Integrating telemetry from:

* service meshes
* API gateways
* tracing systems

to refine attack graphs.

---

### Autonomous Defense

Triggering automated mitigation actions when high-risk paths are detected.

---

# Summary

Pathfinder transforms raw code into a **security-aware architecture model**.

By combining:

* deterministic graph analysis
* knowledge graphs
* attacker intent modeling
* LLM semantic enrichment

the system predicts **how attackers are most likely to move through a system**, explains the result, and recommends mitigations.

The architectural advantage is speed: Pathfinder turns a workflow that usually requires reading advisories, tracing code dependencies, understanding architecture, and planning mitigations by hand into an automated pipeline that can run in seconds.

That is the core cybersecurity value proposition: **AI accelerates understanding and response, reducing MTTR and enabling proactive defense.**
