# Pathfinder

**AI that reduces cyber threat analysis from hours to seconds.**

Pathfinder is an AI-accelerated cybersecurity platform designed to reduce **MTTR — Mean Time To Respond**.

Instead of only listing vulnerabilities, Pathfinder helps answer the question:

> If a vulnerability appears in this system, how would an attacker most likely move through it, and what should we fix first?

## Why Pathfinder

Security teams often spend too long on three things:

* discovering what part of the system is actually affected
* understanding likely attack paths
* deciding the best mitigation point

Pathfinder is built to shrink those delays by combining:

* **code-derived architecture discovery**
* **deterministic graph reasoning**
* **LLM-based interpretation and explanation**

## Core value proposition

Pathfinder is not just an "LLM for security."

It is a hybrid system that:

1. derives architecture from code
2. maps vulnerabilities to services
3. simulates likely attacker movement
4. identifies choke points
5. recommends mitigations

This reframes the product from:

*"a tool that predicts attack paths"*

to:

*"an AI system that reduces the time required to understand and respond to cyber threats."*

## How it works

Pathfinder uses a layered graph model:

`CodeGraph → Service Graph → Attack Graph`

High-level flow:

1. **CodeGraph extraction** captures the codebase structure and symbol dependencies.
2. **Service discovery** infers service boundaries from the code.
3. **Service graph construction** builds service-to-service dependency relationships.
4. **Attack graph reasoning** simulates attacker movement using deterministic scoring.
5. **LLM enrichment** interprets CVEs, explains risk, and proposes mitigations.
6. **Security copilot** lets analysts ask natural-language questions grounded in the graph.

## MTTR-first design

Pathfinder is designed to reduce:

* **threat discovery time**
* **attack path analysis time**
* **mitigation decision time**

Example workflow:

`Vulnerability appears → AI derives architecture → AI predicts attacker path → AI identifies choke points → AI recommends mitigations`

## Example outcome

Input:

`CVE-XXXX affects Auth Service`

Output:

`Internet → Web Service → Auth Service → Billing Service → Payment DB`

Recommended action:

`Patch Auth Service first; add monitoring on Billing API`

## Key capabilities

* code-derived architecture discovery
* instant vulnerability impact analysis
* goal-conditioned attack path prediction
* defensive choke-point identification
* explainable mitigation recommendations
* security copilot queries over the graph

## Repository contents

This repository is currently documentation-first.

Key docs:

* `docs/PRD.md` — product framing, MVP scope, success metrics, and examples
* `docs/ARCHITECTURE.md` — technical design, graph pipeline, and AI/deterministic reasoning model

## Current status

This repo currently contains the product and architecture definition for Pathfinder.

The implementation goal is to demonstrate that AI can compress a workflow that normally takes analysts **hours** into **seconds** for bounded cyber threat analysis scenarios.

## Positioning

Pathfinder can be described in one sentence as:

> Pathfinder uses AI to automatically derive system architecture from code, simulate attacker behavior, and generate mitigation strategies, reducing cyber threat analysis time from hours to seconds.

## Next steps

Likely next implementation milestones:

* build CodeGraph ingestion
* implement service discovery heuristics
* construct the service and attack graphs
* add risk scoring and attacker intent modeling
* add a simple dashboard / copilot demo
