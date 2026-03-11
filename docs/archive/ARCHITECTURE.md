# Pathfinder Architecture

## Overview

Pathfinder is an **AI-accelerated cyber defense system** designed to reduce **Mean Time To Respond (MTTR)** by compressing three expensive parts of cyber analysis:

* **threat discovery time**
* **attack path analysis time**
* **mitigation decision time**

It does this by combining:

* **CodeGraph-grounded structural extraction**
* **LLM service-boundary inference**
* **LLM-generated risk weights**
* **Deterministic path search over validated weighted graphs**

The system automatically derives a **service-level architecture graph** from a codebase using the CodeGraph knowledge graph and an LLM service-inference layer, maps vulnerabilities to affected services, then uses an LLM to assign risk weights from service code and vulnerability context before simulating attacker movement across that weighted architecture.

The goal is to answer questions such as:

* *If an attacker exploits vulnerability X, what is the most likely path to sensitive assets?*
* *Which architectural nodes are critical choke points?*
* *Which services represent the highest security risk?*
* *Which node should we patch, monitor, or segment first?*

The architecture emphasizes **CodeGraph-grounded inference**: deterministic extraction provides structural truth, LLMs infer service abstractions and risk weights, and graph traversal remains deterministic once those outputs have been validated.

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
Candidate Cluster Packaging               │
   │                                      │
   ▼                                      │
LLM Service Boundary Inference            │
   │                                      │
   ▼                                      │
Service Graph Validation + Construction   │
   │                                      │
   └──────────────► LLM Risk Scoring ◄────┘
                          │
                          ▼
             Deterministic Attack Path Search
                          │
                          ▼
        Security Copilot / Explanations / Mitigations
```

Core idea:

* **CodeGraph provides structural truth**
* **LLMs infer service architecture abstractions from graph evidence**
* **LLMs generate risk weights from service code and threat context**
* **Graph algorithms deterministically search attack paths once the graph and weights are validated**
* **The full pipeline is optimized to reduce MTTR from hours to seconds on bounded scenarios**

---

# MTTR Reduction Model

Pathfinder is intentionally designed to remove the main human bottlenecks in cyber response.

## 1. Threat Discovery Time

Pathfinder reduces discovery time by:

* deriving candidate architecture directly from code
* inferring service boundaries automatically from graph evidence
* surfacing affected services automatically
* converting natural-language advisories into structured signals

## 2. Attack Path Analysis Time

Pathfinder reduces analysis time by:

* constructing a validated service graph automatically
* assigning service risk weights automatically from code and vulnerability context
* simulating likely attacker movement over an attack graph
* identifying choke points and crown-jewel exposure immediately

## 3. Mitigation Decision Time

Pathfinder reduces decision time by:

* explaining why a path is risky
* grounding recommendations in graph structure
* allowing analysts to ask targeted questions through a security copilot

What is normally a manual workflow — reading advisories, searching the codebase, tracing dependencies, understanding architecture, and proposing mitigations — is compressed into a single automated pipeline.

---

# Architecture Quality Goals

A strong cybersecurity platform is not judged only on accuracy. Pathfinder's architecture is intentionally designed around the following quality attributes.

## Cost Efficiency

* deterministic graph traversal performs repeated search efficiently once weights are assigned
* LLM cost is concentrated in service-boundary inference and risk scoring, where semantic lift matters most
* architecture outputs, score outputs, and graph artifacts can be cached and reused across many analyses

## Scalability

* the system compresses symbol-level complexity into service-level reasoning
* incremental recomputation can be used when only part of a codebase changes
* independent services can be re-scored without recomputing the full graph
* the graph model can start with NetworkX for MVP and evolve to larger backends if needed

## Security and Robustness

* graph outputs are grounded in code-derived evidence
* service boundaries and risk scores must be schema-validated before use
* high-impact actions are recommendation-first rather than automatically enforced in the MVP
* prompts and outputs can be bounded to avoid leaking unnecessary sensitive context

## Flexibility and Agility

* new attacker goals can be added without redesigning the pipeline
* new input sources such as CVE feeds and runtime telemetry can be attached incrementally
* model providers can be swapped without changing CodeGraph extraction or deterministic traversal

## Novelty

The technical novelty is the combination of **CodeGraph-grounded service inference**, **LLM-generated cyber risk weights**, and **deterministic attack-path search** in a single workflow optimized for cyber response time.

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

# 2. LLM Service Boundary Inference

Pathfinder first extracts **candidate architectural units** from the CodeGraph, then uses an LLM to infer which candidates should become service nodes.

These are potential **service nodes** such as:

* authentication service
* billing service
* notification worker
* admin interface
* agent runtime

Because real architectures are rarely explicit in code, Pathfinder does not rely on directory heuristics alone. Instead, it packages graph-backed candidates and lets the LLM infer service boundaries from structural and semantic evidence.

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

Semantic hints from:

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

These help the LLM identify domain boundaries and distinguish true services from shared utilities.

---

# Candidate Packaging for the LLM

For each candidate, Pathfinder prepares a compact inference bundle containing:

* structural metrics
* dependency direction
* representative files and symbols
* semantic hints
* neighboring candidate relationships

The LLM uses this bundle to decide whether the candidate is:

* a standalone service
* a shared library or utility
* part of a larger service
* an ambiguous cluster that needs review

---

# Validation and Node Promotion

Because candidates often overlap, Pathfinder validates and promotes nodes using deterministic rules after the LLM proposes service boundaries:

1. reject any invented files, symbols, or directories
2. prefer **more specific subtrees** over broad parents when both are proposed
3. avoid promoting both parent and child nodes unless clearly distinct
4. ensure each file belongs to **exactly one promoted service** or a shared utility bucket
5. flag unresolved ambiguity for analyst review

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

All descendant files and symbols become members of that service node once validation succeeds.

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

## LLM Risk Scoring

Services or attack steps are weighted using an LLM-generated risk model.

Inputs to the scoring prompt include:

* service metadata and capability labels
* representative code files
* dependency neighborhood
* vulnerability or CVE context
* attacker goal

Typical numeric outputs include:

```
exploitability
+ reachability
+ privilege_gain
+ goal_alignment
+ downstream_potential
- detection_risk
- segmentation_penalty
```

The LLM can also return:

* confidence
* brief rationale
* evidence references to files, symbols, or edges

These outputs are normalized, bounded, and validated before they become **cost scores** for attacker movement.

Deterministic graph traversal then identifies:

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

Each goal changes the context the LLM uses when generating risk weights.

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

# 6. LLM Architecture, Risk, and Enrichment Layer

LLMs are used for three core responsibilities:

* inferring service boundaries from CodeGraph-backed candidates
* generating numeric risk weights from service code and threat context
* producing analyst-facing explanations and mitigation guidance

Deterministic components still handle CodeGraph extraction, validation, and final path traversal.

---

## Service Boundary Inference

The LLM analyzes candidate clusters and proposes service boundaries, labels, and capabilities.

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
service_name: Authentication Service
classification: standalone_service
confidence: 0.92
responsibilities:
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

This provides **security context** for downstream risk scoring.

---

## Risk Weight Generation

The LLM evaluates service context and emits structured scores that influence traversal.

Example output:

```json
{
  "exploitability": 0.86,
  "privilege_gain": 0.78,
  "goal_alignment": 0.81,
  "detection_risk": 0.32,
  "confidence": 0.74
}
```

These values are validated and normalized before path search runs.

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

These signals inform the LLM risk-scoring step and help map advisories to the right services.

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

The copilot does not invent topology. It answers by retrieving evidence from the CodeGraph, validated Service Graph, and Attack Graph, then uses the LLM to produce concise analyst-facing responses.

## Responsible AI Guardrails

To ensure responsible use of AI, Pathfinder follows these constraints:

* the LLM may propose service boundaries only from CodeGraph-backed candidates; it cannot invent files or symbols
* the LLM emits structured scores and rationales, but does not directly act as the final attack-path engine
* service boundaries and risk weights must be schema-validated and bounded before use
* every explanation should be traceable to known nodes, edges, and vulnerability signals
* autonomous mitigation is out of scope for the MVP unless explicitly reviewed by a human
* prompts should minimize unnecessary sensitive source-code exposure when summaries are sufficient

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

## Why This Is Immediately Useful

Even before full runtime integrations, Pathfinder already helps teams:

* understand architecture faster
* prioritize vulnerabilities with real path context
* identify the first mitigation point to investigate
* communicate technical risk to both engineers and leadership

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

## Grounded Structure

Architecture abstraction is inferred by the LLM, but only over a deterministic CodeGraph and validated candidate set.

---

## Explainability

Every node and edge can be traced back to:

* source files
* symbol dependencies
* validated service-boundary assignments
* validated risk-score outputs and rationales

---

## Layered Graph Model

Pathfinder operates across multiple graph layers:

```
CodeGraph → Service Graph → Attack Graph
```

---

## Hybrid AI + Deterministic Reasoning

LLMs infer service boundaries and generate risk weights, while deterministic components validate those outputs and search paths over the resulting graph.

This hybrid model is what gives Pathfinder:

* fast analysis
* consistent results
* explainable decisions

---

## Conservative but Extensible Implementation

The MVP uses a conservative implementation path:

* bounded codebase ingestion
* CodeGraph-backed candidate generation for service inference
* schema-constrained LLM outputs for service boundaries and risk scores
* NetworkX for graph traversal
* caching for architecture and scoring outputs

This keeps the first version feasible while leaving clear room for enterprise hardening, larger graph stores, and more autonomous workflows.

---

# Future Extensions

Possible future capabilities include:

### Code-Level Attack Paths

Expanding service nodes into symbol-level attack chains.

---

### Better Architecture Inference

Using better candidate generation, community detection, and reviewer feedback to improve LLM service-boundary inference in messy monoliths.

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

* CodeGraph extraction
* knowledge graphs
* attacker intent modeling
* LLM-derived service architecture
* LLM-generated risk weights
* deterministic path search

the system predicts **how attackers are most likely to move through a system**, explains the result, and recommends mitigations.

The architectural advantage is speed: Pathfinder turns a workflow that usually requires reading advisories, tracing code dependencies, understanding architecture, and planning mitigations by hand into an automated pipeline that can run in seconds.

That is the core cybersecurity value proposition: **AI accelerates understanding and response, reducing MTTR and enabling proactive defense.**
