# Product Requirements Document (PRD)

## Pathfinder – AI-Accelerated Cyber Threat Response Platform

---

# 1. Product Overview

**Product Name:** Pathfinder
**Category:** AI-Accelerated Cyber Defense / Threat Response
**Tagline:** *AI that reduces cyber threat analysis from hours to seconds.*
**Primary Goal:** Reduce **Mean Time to Respond (MTTR)** by shrinking the three delays that matter most in cyber response:

* threat discovery time
* attack path analysis time
* mitigation decision time

Pathfinder is not just a tool that predicts attack paths. It is an **AI system that reduces the time required to understand and respond to cyber threats**.

The platform automatically derives architecture from code, maps vulnerabilities to affected services, simulates likely attacker movement, and recommends mitigations. It combines:

* **CodeGraph-grounded graph extraction**
* **LLM-derived service boundary inference**
* **LLM-generated risk weights from service code and vulnerability context**
* **deterministic path traversal over validated graph structure**

Pathfinder models an organization's system as a **goal-conditioned attack graph**, where potential attacker movements are simulated and ranked using LLM-generated numeric risk factors such as:

* exploitability
* network reachability
* privilege escalation potential
* asset value
* attacker objective
* detection risk

Unlike traditional vulnerability scanners that produce long lists of issues, Pathfinder answers the question:

> *If an attacker exploits this vulnerability, what is the most likely path to critical assets?*

The platform predicts **probable attack chains**, identifies **defensive choke points**, and provides **explainable reasoning** for security teams.

When a new vulnerability appears, Pathfinder compresses a workflow that often takes analysts **30 minutes to several hours** into **seconds**:

```text
Vulnerability appears
        ↓
AI derives service architecture from code
        ↓
AI assigns risk weights from code and CVE context
        ↓
Graph engine ranks attacker paths
        ↓
AI identifies choke points
        ↓
AI recommends mitigations
```

---

# 2. Problem Statement

Security teams currently struggle with:

### Alert Overload

Vulnerability scanners generate hundreds of findings with no prioritization based on real attack paths.

### Lack of Context

Security tools identify vulnerabilities but do not explain how they could combine to form a real attack chain.

### Manual Architecture Comprehension

When a CVE appears, analysts often need to reverse-engineer how a codebase maps to services, dependencies, trust boundaries, and crown-jewel assets.

### Vulnerability Interpretation Bottleneck

Security advisories are written in natural language. Analysts must translate descriptions such as *"improper token validation allows privilege escalation"* into concrete architectural risk.

### Slow Response Times

Security analysts must manually:

1. read the vulnerability report
2. identify the affected service
3. search the codebase for usage
4. trace dependencies
5. understand architecture
6. determine impact
7. identify attack paths
8. propose mitigations

This often takes **30 minutes to several hours**, especially in large systems.

### Rise of Autonomous Attacks

With AI-driven cyber threats and automated exploitation frameworks, attackers can rapidly explore infrastructure weaknesses.

Organizations need tools that can:

* simulate attacker behavior
* identify likely attack paths
* prioritize defenses
* explain risk clearly

---

# 3. Product Vision

Pathfinder provides **defensive autonomy** by combining **CodeGraph-grounded AI understanding** with **deterministic graph traversal**.

The system:

1. Derives a **CodeGraph** from the codebase
2. Uses an LLM to infer **service nodes, service boundaries, and capabilities** from graph evidence
3. Validates those outputs and constructs a **Service Graph**
4. Uses an LLM to translate service code and CVE context into **structured risk weights**
5. Runs deterministic path search over a weighted **goal-conditioned Attack Graph**
6. Explains the reasoning and recommends mitigations

The result is a **live, explainable security model** that moves teams from reactive investigation to proactive response.

### Immediate Value Delivered by the MVP

Even a bounded first version of Pathfinder delivers practical value:

* it shortens triage for a newly disclosed vulnerability
* it gives analysts an architectural view without manual code archaeology
* it prioritizes the first mitigation action instead of producing another long list
* it creates a demoable foundation for a larger autonomous defense roadmap

### Why This Product Is Feasible

The MVP is intentionally conservative in scope:

* architecture is derived from a bounded codebase rather than every possible enterprise system
* service-node inference and risk scoring are AI-driven but constrained by CodeGraph evidence
* attack-path traversal remains deterministic once validated weights are assigned
* LLM outputs can be schema-validated, cached, and reviewed before use
* the system can show immediate value before requiring deep runtime integrations

---

# 4. Target Users

### Primary Users

Security Operations Center (SOC) Analysts
Responsible for monitoring threats and responding to incidents.

### Secondary Users

Security Architects
Responsible for infrastructure design and risk management.

### Tertiary Users

CISOs and Security Leadership
Require strategic visibility into systemic risk.

### User Outcomes

SOC Analyst outcomes:

* know which path matters first
* know what to patch or monitor first
* reduce time spent manually tracing service dependencies

Security Architect outcomes:

* identify risky trust boundaries and choke points
* evaluate segmentation and hardening opportunities
* reason about system-wide blast radius

Leadership outcomes:

* understand why a threat matters
* see a defensible prioritization narrative
* justify investment in proactive cyber defense

---

# 5. Key Product Capabilities

Pathfinder provides the following core capabilities:

### AI-Derived Service Architecture

Pathfinder automatically derives a security-relevant architecture from source code by combining CodeGraph evidence with LLM service-boundary inference.

Layered graph model:

```text
CodeGraph → Service Graph → Attack Graph
```

The LLM defines service nodes from graph-backed candidates such as:

* authentication service
* billing service
* notification worker
* admin interface
* shared database access layer

Example relationships:

* service dependencies
* network reachability
* credential trust
* API permissions

---

### Instant Vulnerability Impact Analysis

Given a CVE or vulnerability description, Pathfinder can:

* map the issue to the affected service
* identify likely downstream assets at risk
* simulate likely attacker movement
* surface choke points and recommended mitigations

This is the clearest demonstration that **AI accelerates cybersecurity by reducing MTTR**.

---

### Goal-Conditioned Attack Simulation

Attack paths are calculated based on **attacker intent**.

Supported attacker goals include:

* data exfiltration
* ransomware deployment
* financial fraud
* persistence
* system sabotage

Each goal dynamically changes how the LLM scores risk factors and how the graph engine ranks paths.

---

### LLM-Based Risk Estimation and Deterministic Path Search

Using LLM-generated risk factors plus weighted graph traversal, Pathfinder predicts:

* most likely attack path
* top 3 attack paths
* path risk scores
* estimated attacker progress

The LLM outputs structured numeric risk values for services or attack steps, and the graph engine deterministically searches over those validated weights.

---

### Defensive Choke Point Identification

Pathfinder identifies nodes that appear across multiple attack paths.

These nodes represent optimal locations to deploy defenses such as:

* monitoring
* access restrictions
* patching
* network segmentation

---

### Explainable Security Intelligence

For each predicted attack path, the system provides:

* human-readable explanation
* reasoning chain
* vulnerability contribution
* suggested mitigations

This transparency is essential for trust, analyst adoption, and executive reporting.

---

### Security Copilot Queries

Analysts can ask grounded questions over the graph, such as:

* Which services could lead to database compromise?
* What is the most likely ransomware path?
* Which node should we patch first?

This makes Pathfinder feel like an **AI security analyst assistant**, while keeping responses anchored in validated graph outputs and LLM-generated scores.

---

# 6. Core Concepts

## Attack Graph

A directed graph where:

Nodes represent assets or services.

Edges represent possible attacker movement.

Example:

```
Internet
   ↓
Web Server
   ↓
Auth API
   ↓
User Database
```

---

## Attacker Entry Point

The initial compromised system.

Examples:

* internet-facing web server
* phishing-compromised employee machine
* vulnerable API endpoint

---

## Crown Jewel Assets

High-value targets attackers want to reach.

Examples:

* customer databases
* payment systems
* secrets vaults
* identity systems

---

## Attacker Intent

The attacker’s goal, which determines path weighting.

Supported intents:

Data Exfiltration
Ransomware Deployment
Persistence
Financial Fraud
System Sabotage

---

## Attack Path

A sequence of nodes representing attacker movement.

Example:

```
Internet
→ Web App
→ Auth API
→ Admin Console
```

---

## Layered Graph Model

Pathfinder operates across three graph layers:

```text
CodeGraph → Service Graph → Attack Graph
```

This layered approach is what allows Pathfinder to move from raw code to fast, explainable cyber risk analysis.

---

# 7. System Architecture

## Core Components

### CodeGraph Extraction

Converts the codebase into a structured graph of repositories, directories, files, and symbols.

Responsibilities:

* capture dependency structure
* record symbol usage relationships
* provide structural truth for downstream inference

---

### LLM Service Architecture Engine

Uses the CodeGraph, representative files, dependency summaries, and graph candidates to infer service boundaries and service capabilities.

Responsibilities:

* package graph-backed candidate clusters
* infer service names and capabilities
* assign files and symbols to service nodes
* emit confidence, rationale, and evidence references

---

### Service Graph Validation and Construction

Builds a validated service-level dependency graph from cross-service symbol usage and LLM-inferred service membership.

Responsibilities:

* reject invented files, symbols, or services
* identify service-to-service dependencies
* resolve overlaps or flag ambiguity
* weight edges by dependency strength
* expose architecture for attack reasoning

---

### Attack Graph Traversal Engine

Responsible for storing and traversing the weighted attack graph derived from the service graph.

Technologies:

* Python
* NetworkX

Responsibilities:

* node management
* edge management
* graph traversal
* path search over validated weights

---

### LLM Risk Scoring Engine

Generates structured numeric risk values from:

* service metadata
* selected code files
* dependency context
* vulnerability or CVE context
* attacker goal

Typical outputs include:

* exploitability
* privilege gain
* goal alignment
* downstream potential
* detection risk
* confidence score
* rationale and evidence references

Attacker goals such as `data_exfiltration`, `ransomware`, and `financial_fraud` are included in the scoring prompt and change the resulting weights.

---

### LLM Explanation and Mitigation Engine

LLMs are used for:

* summarizing attack paths
* explaining reasoning
* generating mitigation advice

LLMs are also used to infer service architecture and risk weights, but final path traversal remains deterministic once those outputs have been validated.

---

### Security Copilot and Visualization Dashboard

Provides a visual representation of:

* AI-inferred service architecture
* service graph
* predicted attack paths
* risk scores
* defensive choke points

It also provides a grounded analyst interface for natural-language security questions over the graph.

Frontend technologies may include:

* React
* Cytoscape.js
* D3.js

## Product Design Requirements

### Cost Efficiency

Pathfinder should use LLMs where semantic lift materially improves architecture inference and risk estimation.

To control cost, the system should cache service-boundary outputs and risk scores, re-score only changed or relevant services, and keep path traversal deterministic and inexpensive.

### Scalability

Pathfinder should compress large codebases into service-level abstractions so analysts can reason about systems that are too large to understand manually.

The architecture should support incremental updates, bounded top-k path outputs, and eventually pluggable graph backends for larger environments.

### Security and Trust

Recommendations must be grounded in CodeGraph evidence, validated service-node memberships, and schema-constrained LLM score outputs.

The system should show why a path was predicted, which vulnerability signals mattered, which files contributed to the inferred service boundary, and which architectural edges enabled the result.

### Responsible AI Use

LLMs are used to infer service boundaries and estimate risk, but their outputs must be schema-constrained, validated against the CodeGraph, and reviewable by human analysts.

The LLM should never invent files, symbols, or services that do not exist in the underlying graph, and high-impact recommendations should remain reviewable by humans.

### Flexibility and Agility

The product should support multiple codebases, attacker goals, risk models, and future telemetry sources without redesigning the full system.

This is important both for hackathon feasibility and for long-term productization.

---

# 8. Data Model

## Node Schema

Example node attributes:

```
service_id
root_directory
file_count
symbol_count
exported_symbol_count
capabilities
service_members
llm_boundary_confidence
boundary_rationale
criticality
internet_exposed
risk_score
llm_risk_score
risk_factors
risk_rationale
evidence_files
scoring_model_version
vulnerability_signals
```

---

## Edge Schema

Example edge attributes:

```
source_service
target_service
dependency_count
risk_weight
reachability
trust_strength
segmentation_penalty
monitoring_level
```

---

## Attacker Profile Schema

Example:

```
goal
risk_tolerance
stealth_preference
speed_preference
```

Each profile influences the LLM-generated scoring weights used by the risk engine.

---

# 9. Risk Weight Generation Model

The LLM generates structured numeric risk values for each service or attack step using:

* service code and metadata
* dependency neighborhood
* vulnerability context
* attacker goal

Typical score factors include:

```
exploitability
+ reachability
+ privilege_gain
+ goal_alignment
+ downstream_potential
- detection_risk
- segmentation_penalty
```

These outputs are normalized, bounded, and validated before being used as weights in the attack graph.

Deterministic graph traversal then identifies:

* minimum-cost attack path
* top candidate paths

---

# 10. Core Workflow

### Step 1: Codebase Ingestion and CodeGraph Extraction

The source code is converted into a CodeGraph.

### Step 2: LLM Service Boundary Inference

The system packages graph-backed candidate clusters and uses an LLM to infer service nodes, boundaries, and capabilities.

### Step 3: Service Graph Validation and Construction

The inferred service nodes are validated against the CodeGraph and assembled into a Service Graph.

### Step 4: Vulnerability Interpretation and LLM Risk Scoring

Known vulnerabilities or CVEs are translated into structured signals and combined with service code to produce numeric risk weights.

### Step 5: Attacker Entry and Goal Defined

User selects or confirms an entry point and attacker objective.

### Step 6: Attack Path Simulation

Graph engine calculates attack paths over the validated weighted graph.

### Step 7: Choke Point and Risk Ranking

Paths are ranked by likelihood and defensive leverage.

### Step 8: Explainability Layer

LLM generates explanations, score rationales, and mitigation advice.

### Step 9: Visualization and Copilot Querying

Dashboard displays attack paths, defensive insights, and grounded answers to analyst questions.

---

# 11. MVP Scope

The hackathon MVP will include:

### AI-Derived Architecture

LLM-assisted service-node inference from a bounded demo codebase using CodeGraph-backed candidates.

### Service and Attack Graphs

Construction of a validated service graph and attack graph from the inferred architecture.

### LLM Risk Scoring

Generate numeric risk weights from selected service files, dependency context, CVE context, and attacker goal.

### Attack Simulation

Single entry point with 3 attacker goals.

### Instant Vulnerability Impact Analysis

Input a vulnerability or affected service and immediately surface likely attack paths and at-risk assets.

### Path Prediction

Compute top 3 attack paths using deterministic traversal over LLM-generated weights.

### Visualization

Interactive graph showing predicted paths.

### Explanation Engine

LLM-generated explanation of attack reasoning, service-boundary rationale, and mitigation recommendations.

### Security Copilot

Grounded natural-language questions over the graph for demo scenarios.

### Demo-Ready Storytelling

The MVP should support two levels of explanation:

* a **10-second viewer** immediately sees the vulnerability input, attack path, and first mitigation recommendation
* a **deeper technical viewer** can inspect architecture derivation, graph reasoning, and why the recommendation is justified

---

# 12. Success Metrics

### MTTR Reduction

Measure end-to-end vulnerability impact analysis time.

Target benchmark for representative scenarios:

| Task | Manual | Pathfinder |
| --- | --- | --- |
| Understand architecture | 30–60 min | seconds |
| Trace dependencies | 20–40 min | seconds |
| Identify attack paths | 30–60 min | seconds |
| Generate mitigation plan | 15–30 min | seconds |

Goal:

Reduce representative analysis from **hours to under 10 seconds** for bounded demo scenarios.

---

### Path Prediction Accuracy

Validate predicted paths against known attack scenarios.

---

### Scoring Quality and Consistency

Measure whether LLM-generated service boundaries and risk scores are stable, schema-valid, and reviewer-aligned.

Signals include:

* service nodes map only to real files and symbols
* risk outputs are numeric, bounded, and parseable
* repeated runs produce acceptably similar rankings

---

### Analyst Productivity

Measure reduction in time spent prioritizing vulnerabilities.

---

### Responsible AI Quality

Measure whether outputs remain grounded in CodeGraph evidence and validated graph structure.

Signals include:

* inferred service nodes reference actual files and symbols
* explanations reference actual nodes and edges
* mitigation advice maps to identified choke points
* no unsupported architecture or score claims are introduced by the LLM

---

# 13. Example Scenario

Initial Signal:

```
CVE-2026-XXXX affects Auth Service
```

Derived Architecture Context:

```
Internet → Web Service → Auth Service → Billing Service → Payment DB
```

Attacker Goal:

```
Data Exfiltration
```

Predicted Attack Path:

```
Internet
→ Web Service
→ Auth Service
→ Billing Service
→ Payment DB
```

System Explanation:

The LLM infers an authentication service and billing service from CodeGraph-backed file clusters, then scores the Auth Service highly for exploitability and privilege gain given the CVE context. The weighted service graph shows that the web service depends on auth, auth has privileged access to billing workflows, and billing reaches payment data. Pathfinder therefore ranks the path from internet-facing web entry to payment data as a likely data-exfiltration route.

Recommended Mitigation:

* patch the Auth Service vulnerability
* add monitoring on the Billing API boundary
* restrict Payment DB access from non-essential services
* prioritize the Auth Service as the first remediation point

Expected Analysis Time:

```text
seconds
```

---

# 14. Roadmap and Next Iterations

Potential future capabilities include:

### Next Iteration 1: Live Vulnerability Intake

Integrate CVE feeds or analyst-submitted advisories and trigger immediate impact analysis.

### Next Iteration 2: Better Architecture Inference

Improve LLM service-boundary inference in large monoliths and messy repositories.

### Next Iteration 3: Scoring Calibration and Cost Optimization

Improve prompt design, caching, confidence calibration, and reviewer feedback loops for LLM-generated risk weights.

### Next Iteration 4: Runtime Context

Incorporate tracing, API gateway, and service-mesh telemetry.

### Next Iteration 5: Analyst Feedback Loop

Allow analysts to confirm, reject, and refine predicted paths to improve prioritization quality.

### Next Iteration 6: Autonomous Defense

Trigger controlled mitigation workflows such as ticket creation, monitoring updates, or policy recommendations.

### Next Iteration 7: Agentic Security Monitoring

Extend protection to internal AI agents and agent-to-agent trust paths.

### Next Iteration 8: Simulation and Training Mode

Run full cyber attack simulations for tabletop exercises and training.

---

# 15. Strategic Value

Pathfinder transforms vulnerability management from:

**"What vulnerabilities exist?"**

to

**"How would an attacker actually use them?"**

By inferring architecture from CodeGraph evidence, generating risk weights from service code, predicting attack paths, and explaining defensive choke points, the system enables organizations to **prioritize security where it matters most**.

The result is faster detection, faster response, stronger resilience against modern cyber threats, and a clear demonstration that **AI can reduce MTTR by compressing hours of security analysis into seconds**.
