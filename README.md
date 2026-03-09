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

* **code-derived structural file-graph extraction**
* **deterministic graph reasoning**
* **LLM-based file and edge analysis**

## Core value proposition

Pathfinder is not just an "LLM for security."

It is a hybrid system that:

1. builds a structural graph of source files and their relationships
2. runs one LLM analysis per file to identify likely target files and assign node risk
3. runs one LLM analysis per structural edge to derive attack edges and traversal cost
4. ranks likely attacker paths from entry-like files to target files
5. identifies choke points and recommends mitigations

This reframes the product from:

*"a tool that predicts attack paths"*

to:

*"an AI system that reduces the time required to understand and respond to cyber threats."*

## How it works

Pathfinder uses a layered file-level graph model:

`Repository → Structural File Graph → Attack Graph`

High-level flow:

1. **Structural extraction** captures source files and file-to-file relationships.
2. **Per-file LLM analysis** assigns `target_flag` and node risk for each file.
3. **Per-structural-edge LLM analysis** derives attack edges and traversal cost.
4. **Attack path search** ranks likely attacker paths deterministically once scores are assigned.
5. **Explanation** highlights why the destination matters and where to mitigate first.

## MTTR-first design

Pathfinder is designed to reduce:

* **threat discovery time**
* **attack path analysis time**
* **mitigation decision time**

Example workflow:

`Repository ingested → Structural graph built → File/edge LLM analysis runs → Attack path ranked → Choke points explained`

## Example outcome

Input:

`Repository contains exposed auth logic, admin routes, and permissions storage`

Output:

`auth_handler.py → session_manager.py → admin_access.py → permissions_store.py`

Recommended action:

`Harden auth_handler.py first; inspect authorization in admin_access.py`

## Key capabilities

* code-derived structural file-graph extraction
* file-level attack path prediction
* target-file risk ranking
* defensive choke-point identification
* explainable mitigation recommendations
* attack-edge reasoning grounded in structural evidence

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

> Pathfinder builds a structural file graph, uses one LLM pass per file to assign `target_flag` and target risk, uses one LLM pass per structural edge to derive attack edges and traversal cost, and then ranks likely attacker paths deterministically.

## Next steps

Likely next implementation milestones:

* build repository and structural-edge ingestion
* implement per-file target/risk analysis
* implement per-structural-edge attack-edge generation
* add deterministic path search over attack edges
* add a simple dashboard / copilot demo
