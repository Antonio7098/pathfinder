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

* **CodeGraph-based architecture discovery**
* **deterministic graph reasoning**
* **LLM semantic interpretation and explanation**

Pathfinder models an organization's system as a **goal-conditioned attack graph**, where potential attacker movements are simulated and ranked based on:

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
AI derives architecture from code
        ↓
AI predicts attacker path
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

Pathfinder provides **defensive autonomy** by combining **AI semantic understanding** with **deterministic graph-based reasoning**.

The system:

1. Derives a **CodeGraph** from the codebase
2. Discovers service boundaries and constructs a **Service Graph**
3. Converts the Service Graph into a **goal-conditioned Attack Graph**
4. Translates CVEs and threat descriptions into structured risk signals
5. Predicts ranked attacker paths and defensive choke points
6. Explains the reasoning and recommends mitigations

The result is a **live, explainable security model** that moves teams from reactive investigation to proactive response.

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

---

# 5. Key Product Capabilities

Pathfinder provides the following core capabilities:

### Code-Derived Architecture Discovery

Pathfinder automatically derives a security-relevant architecture from source code.

Layered graph model:

```text
CodeGraph → Service Graph → Attack Graph
```

Example service nodes:

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

Each goal dynamically changes how attack paths are weighted.

---

### Deterministic Attack Path Ranking

Using weighted graph traversal, Pathfinder predicts:

* most likely attack path
* top 3 attack paths
* path risk scores
* estimated attacker progress

Core path prediction remains **deterministic and explainable**, while AI is used to interpret inputs and explain outputs.

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

This makes Pathfinder feel like an **AI security analyst assistant**, while keeping responses anchored in deterministic graph results.

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

### Service Discovery Engine

Infers likely service boundaries from the CodeGraph using deterministic heuristics.

Responsibilities:

* candidate service generation
* service-likeness scoring
* promotion of service nodes
* assignment of files and symbols to services

---

### Service Graph Construction

Builds a service-level dependency graph from cross-service symbol usage.

Responsibilities:

* identify service-to-service dependencies
* weight edges by dependency strength
* expose architecture for attack reasoning

---

### Attack Graph Engine

Responsible for storing and traversing the attack graph derived from the service graph.

Technologies:

* Python
* NetworkX

Responsibilities:

* node management
* edge management
* graph traversal
* path scoring

---

### Risk Scoring and Attacker Intent Model

Calculates traversal scores using factors such as:

* exploitability
* privilege gain
* goal alignment
* detection risk
* network segmentation

Attacker goals such as `data_exfiltration`, `ransomware`, and `financial_fraud` dynamically adjust risk weights.

---

### LLM Reasoning Engine

LLMs are used for:

* labeling and summarizing services
* summarizing attack paths
* explaining reasoning
* translating CVE descriptions into structured risk signals
* generating mitigation advice

LLMs are **not used for core path prediction**, which remains deterministic.

---

### Security Copilot and Visualization Dashboard

Provides a visual representation of:

* code-derived architecture
* service graph
* predicted attack paths
* risk scores
* defensive choke points

It also provides a grounded analyst interface for natural-language security questions over the graph.

Frontend technologies may include:

* React
* Cytoscape.js
* D3.js

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
criticality
internet_exposed
risk_score
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

Each profile defines scoring weights used by the risk engine.

---

# 9. Risk Scoring Model

Traversal score considers:

```
exploitability
+ reachability
+ privilege_gain
+ goal_alignment
+ downstream_potential
- detection_risk
- segmentation_penalty
```

This produces a cost score for each movement.

Graph traversal then identifies:

* minimum-cost attack path
* top candidate paths

---

# 10. Core Workflow

### Step 1: Codebase Ingestion and CodeGraph Extraction

The source code is converted into a CodeGraph.

### Step 2: Service Discovery and Architecture Derivation

The system discovers service boundaries and constructs a Service Graph.

### Step 3: Vulnerability Interpretation

Known vulnerabilities or CVEs are translated into structured signals and mapped to affected services.

### Step 4: Attacker Entry and Goal Defined

User selects or confirms an entry point and attacker objective.

### Step 5: Attack Path Simulation

Graph engine calculates attack paths.

### Step 6: Choke Point and Risk Ranking

Paths are ranked by likelihood and defensive leverage.

### Step 7: Explainability Layer

LLM generates explanations and mitigation advice.

### Step 8: Visualization and Copilot Querying

Dashboard displays attack paths, defensive insights, and grounded answers to analyst questions.

---

# 11. MVP Scope

The hackathon MVP will include:

### Code-Derived Architecture

Automatic service discovery from a bounded demo codebase.

### Service and Attack Graphs

Construction of a service graph and attack graph from the derived architecture.

### Attack Simulation

Single entry point with 3 attacker goals.

### Instant Vulnerability Impact Analysis

Input a vulnerability or affected service and immediately surface likely attack paths and at-risk assets.

### Path Prediction

Compute top 3 attack paths.

### Visualization

Interactive graph showing predicted paths.

### Explanation Engine

LLM-generated explanation of attack reasoning and mitigation recommendations.

### Security Copilot

Grounded natural-language questions over the graph for demo scenarios.

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

### Analyst Productivity

Measure reduction in time spent prioritizing vulnerabilities.

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

The CVE maps to the authentication service. The derived service graph shows that the web service depends on auth, auth has privileged access to billing workflows, and billing reaches payment data. Pathfinder therefore ranks the path from internet-facing web entry to payment data as a likely data-exfiltration route.

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

# 14. Future Enhancements

Potential future capabilities include:

Automatic Architecture Discovery
Improve service discovery in large monoliths and messy repositories.

Real-Time Threat Feeds
Integrate CVE databases and threat intelligence.

Runtime Integration
Incorporate tracing, API gateway, and service-mesh telemetry.

Autonomous Defense
Trigger automatic security responses.

Agentic Security Monitoring
Extend protection to internal AI agents.

Simulation Mode
Run full cyber attack simulations for training.

---

# 15. Strategic Value

Pathfinder transforms vulnerability management from:

**"What vulnerabilities exist?"**

to

**"How would an attacker actually use them?"**

By deriving architecture from code, predicting attack paths, and explaining defensive choke points, the system enables organizations to **prioritize security where it matters most**.

The result is faster detection, faster response, stronger resilience against modern cyber threats, and a clear demonstration that **AI can reduce MTTR by compressing hours of security analysis into seconds**.
