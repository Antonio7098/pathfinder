# Evaluation System

This document explains Pathfinder's evaluation framework for the LLM-backed security analysis stages.

The evaluation system measures two separate tasks:

* **file-level security risk classification**
* **attack-edge identification from structural edges**

It is designed to stay aligned with Pathfinder's core rules:

* files remain the canonical MVP node
* structural extraction remains authoritative
* attack edges are only evaluated on top of real structural edges
* results are persisted as typed, reviewable artifacts

## Goals

The evaluation system exists to answer questions like:

* How accurate is a model at assigning file risk?
* How accurate is a model at deciding whether a structural edge should become an attack edge?
* How accurate is a model at assigning attack types and edge traversal cost?
* What token, latency, and cost footprint does a run have?

## What is being evaluated

### 1. File-risk evaluation

For each file case in a golden dataset, Pathfinder compares the model output against a manually assigned gold expectation.

Each gold file case contains:

* `file_path`
* `expected_risk_score`
* `expected_risk_label`
* manual rationale

The evaluator consumes the same structured file-security output used by the main pipeline, including:

* `normalized_risk_score`
* supporting security subscores
* confidence
* rationale

### 2. Attack-edge evaluation

For each structural edge case in a golden dataset, Pathfinder compares the model output against a manual gold judgment.

Each gold edge case contains:

* `structural_edge_id`
* `source_path`
* `target_path`
* `relationship_type`
* whether an attack edge should exist at all
* expected attack types for positive cases
* optional expected `edge_attack_cost`
* manual rationale

This is important: the evaluator does **not** ask the model to score arbitrary file pairs. It only evaluates real structural edges.

## Golden dataset

The current manual golden dataset lives at:

* `tests/fixtures/security_eval/demo_vuln_repo_golden_dataset.json`

It is grounded in the demo vulnerable repository:

* `tests/fixtures/demo_vuln_repo`

The dataset includes both:

* **positive** attack-edge examples
* **negative** attack-edge examples

Negative examples are especially important because they measure whether the model over-generates attack edges. In the current gold set, some `imports` relationships are intentionally labeled negative even when the corresponding `calls` edge is positive.

## Run artifacts

Each evaluation run produces a persisted JSON artifact containing:

* dataset identity
* provider and model
* optional model profile metadata
* pricing used for cost estimation
* per-file results
* per-edge results
* aggregate metrics
* diagnostics
* runtime usage statistics

Example output locations:

* `artifacts/evaluation/openrouter_demo_vuln_repo_eval.json`
* `artifacts/evaluation/minimax_demo_vuln_repo_eval.json`

## Metrics

### File-risk metrics

Key file-risk metrics include:

* `label_accuracy` — exact 4-way label match across `low`, `medium`, `high`, `critical`
* `score_mean_absolute_error` — average absolute error between predicted and gold risk score
* `high_risk_precision` — precision for the binary decision "is this file high risk?"
* `high_risk_recall` — recall for that same binary decision
* `high_risk_f1` — F1 for that same binary decision

For binary high-risk metrics:

* `high` and `critical` are treated as high-risk
* `low` and `medium` are treated as not high-risk

### Attack-edge metrics

Key edge metrics include:

* `presence_accuracy` — was the binary attack-edge presence decision correct?
* `presence_precision` — of predicted attack edges, how many were real positives?
* `presence_recall` — of gold-positive attack edges, how many were found?
* `presence_f1` — harmonic mean of presence precision and recall
* `relaxed_attack_type_accuracy` — for positive cases, did the model predict at least one correct attack type?
* `exact_attack_type_accuracy` — for positive cases, did the full attack-type set exactly match?
* `top_1_attack_type_accuracy` — was the first predicted attack type a gold attack type?
* `edge_attack_cost_mean_absolute_error` — average absolute error for predicted edge traversal cost

### Runtime and cost metrics

Each run also records operational metrics:

* `total_input_tokens`
* `total_output_tokens`
* `total_tokens`
* `total_duration_seconds`
* `average_duration_seconds`
* `median_duration_seconds`
* `p95_duration_seconds`
* `max_duration_seconds`
* `estimated_total_cost_usd`

These metrics make model-quality comparisons possible without ignoring cost and latency.

## Pricing

The evaluation framework supports two pricing paths:

* explicit CLI-provided pricing
* built-in model pricing profiles

If CLI pricing is provided, it takes precedence.

The repository currently includes a built-in profile for:

* `minimax` / `MiniMax-M2.5`

with:

* total context: `196600`
* max output: `196600`
* input price: `$0.30 / 1M tokens`
* output price: `$1.20 / 1M tokens`

## Running an evaluation

Use the CLI command:

`python -m pathfinder.cli run-security-eval --dataset tests/fixtures/security_eval/demo_vuln_repo_golden_dataset.json --output artifacts/evaluation/my_eval.json --provider minimax --model MiniMax-M2.5`

Optional flags:

* `--repo` to override the dataset repo path
* `--risk-threshold` to control binary high-risk scoring
* `--timeout-seconds` for per-request timeout
* `--max-output-tokens` to constrain model output
* `--input-token-price-per-1m-usd` and `--output-token-price-per-1m-usd` to override built-in pricing

## How to read results

When comparing runs, the most useful summary fields are usually:

* file quality: `label_accuracy`, `high_risk_f1`, `score_mean_absolute_error`
* edge quality: `presence_f1`, `relaxed_attack_type_accuracy`, `top_1_attack_type_accuracy`
* efficiency: `total_tokens`, `average_duration_seconds`, `estimated_total_cost_usd`

In general:

* higher accuracy / precision / recall / F1 is better
* lower MAE is better
* lower latency and lower cost are better

## Design boundaries

The evaluation system is intentionally bounded:

* it does not invent structural edges
* it does not evaluate non-grounded file pairs
* it evaluates the existing per-file and per-structural-edge LLM tasks
* it persists artifacts separately from structural, attack-graph, and search artifacts

This keeps the evaluation system aligned with Pathfinder's explainability and provenance requirements.