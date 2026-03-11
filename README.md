# Pathfinder

Pathfinder is a service-centric cybersecurity analysis system aimed at answering:

> Given a codebase, what is the most likely path an attacker would take through the system, and what should be fixed first?

Pathfinder's service view is derived from grounded file-level structural evidence. The structural graph remains authoritative, while service grouping, service-to-service edges, security analysis, path selection, and recommendation reporting build on top of it.

## Current workflow

Pathfinder's shipped workflow is:

1. ingest a repository with CodeGraph-backed structural extraction
2. project a deterministic file-level structural graph
3. infer grounded service groupings from known files
4. build a deterministic service graph from structural evidence
5. evaluate likely attacker movement on either the service graph or file graph
6. select a likely attack path and generate a grounded recommendation report
7. render a dashboard for review

The default end-to-end experience is **service-centric**: the full pipeline runs in `service` graph mode unless you explicitly choose `file` mode.

## Local setup

### Requirements

* Python `3.12+`

### Create a virtual environment and install Pathfinder

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

After installation, you can use either:

* `python -m pathfinder.cli ...`
* `pathfinder ...`

### Environment configuration

LLM-backed commands read configuration from either:

* environment variables in your shell, or
* a `.env` file in the repository root

Supported variables:

* `OPENROUTER_API_KEY`
* `OPENROUTER_MODEL_ID`
* `MINIMAX_API_KEY`
* `MINIMAX_MODEL_ID`

`MINIMAX_MODEL_ID` is optional and defaults to `MiniMax-M2.5`. For OpenRouter, both the API key and model id must be configured unless you override the model on the CLI.

Example `.env`:

```bash
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL_ID=openai/gpt-4.1-mini

MINIMAX_API_KEY=your-key
MINIMAX_MODEL_ID=MiniMax-M2.5
```

## Main commands

Run the full demo pipeline:

```bash
python -m pathfinder.cli run-full-pipeline \
  --repo tests/fixtures/demo_vuln_repo \
  --output-dir demo-output \
  --graph-mode service \
  --provider minimax \
  --timeout-seconds 600
```

Then open the generated dashboard:

```bash
xdg-open demo-output/dashboard.html
```

Build a structural graph:

* `python -m pathfinder.cli build-structural-graph --repo /path/to/repo --output structural_graph.json`

Optionally also persist raw CodeGraph output:

* `python -m pathfinder.cli build-structural-graph --repo /path/to/repo --output structural_graph.json --raw-codegraph-output raw_codegraph.json`

Infer services from a structural graph artifact:

* `python -m pathfinder.cli identify-services --input structural_graph.json --output service_grouping.json`

Build a deterministic service graph from structural graph + grouping artifacts:

* `python -m pathfinder.cli build-service-graph --structural-graph structural_graph.json --grouping service_grouping.json --output service_graph.json`

Generate a recommendation report from a selected path input artifact:

* `python -m pathfinder.cli generate-recommendation-report --input recommendation_input.json --output recommendation_report.json`

Run the evaluation framework against the demo golden dataset:

* `python -m pathfinder.cli run-security-eval --dataset tests/fixtures/security_eval/demo_vuln_repo_golden_dataset.json --repo tests/fixtures/demo_vuln_repo --output artifacts/evaluation/demo_vuln_repo_eval.json --provider minimax`

See the full CLI surface:

* `python -m pathfinder.cli --help`

## Demo fixture

A small intentionally vulnerable demo repo is available at:

* `tests/fixtures/demo_vuln_repo`

It is designed to produce a readable service graph with a few purposeful vulnerabilities:

* weak token handling in `auth/session.py`
* IDOR and unsafe SQL construction in `billing/payments.py`
* weak admin gate in `admin/export.py`

## Output artifacts

The full pipeline writes a reviewable set of artifacts into the chosen output directory:

* `structural_graph.json`
* `raw_codegraph.json`
* `service_grouping.json`
* `service_graph.json`
* `security_graph.json`
* `recommendation_input.json`
* `recommendation_report.json`
* `dashboard.html`

### Structural grounding

The structural graph artifact contains:

* `file` nodes
* `structural_edges`
* `summary`
* `diagnostics`

### Service grouping and service graph

The service layer adds two versioned artifacts:

* `ServiceGroupingArtifact` — LLM-proposed service groups resolved into grounded file assignments
* `ServiceGraphArtifact` — deterministic service-to-service edges aggregated from structural file edges

These service artifacts do **not** replace the canonical file-level structural graph.

### Security graph and recommendation report

The security/reporting flow produces:

* a `security_graph.json` artifact for the selected graph mode
* a `recommendation_input.json` artifact with ordered path nodes, ordered path edges, and focal files
* a `recommendation_report.json` artifact with path overview, prioritized recommendations, mitigation steps, diagnostics, and LLM invocation audit metadata
* a `dashboard.html` view for interactive review

## Testing

Run the automated test suite with:

```bash
pytest
```

For targeted checks during development, you can run a specific file such as:

* `pytest tests/test_full_pipeline_cli.py`

## LLM usage and observability

Pathfinder includes a reusable LLM layer for service grouping, security evaluation, and recommendation reporting.

Current observability includes:

* prompt template version
* prompt version
* rendered prompts
* prompt hashes
* provider/model metadata
* request id
* token usage when available
* timing and file-context diagnostics

## Repository layout

Important directories:

* `pathfinder/adapters/` — CodeGraph integration and adapter models
* `pathfinder/structural/` — structural graph models, projection, IDs, I/O, and extraction service
* `pathfinder/services/` — service grouping models, graph-building logic, resolvers, I/O, and service layer
* `pathfinder/security_evaluators/` — security-analysis helpers used by the pipeline
* `pathfinder/pipeline/` — full end-to-end pipeline request/result models and orchestration
* `pathfinder/reporting/` — recommendation input/output models, file-context loading, I/O, and service layer
* `pathfinder/dashboard/` — dashboard graph construction and HTML visualisation helpers
* `pathfinder/evaluation/` — evaluation models, metrics, pricing, I/O, and evaluation service
* `pathfinder/llm/` — provider config, adapters, interfaces, and centralized versioned prompts
* `pathfinder/observability/` — structured logging helpers
* `tests/` — fixtures and automated tests
* `docs/` — product, architecture, schema, evaluation, and implementation docs
* `artifacts/` — example evaluation outputs and saved run artifacts

## Key docs

* `docs/ARCHITECTURE.md` — architecture and phase boundaries
* `docs/ATTACK_GRAPH_ENGINE.md` — attack path construction and dashboard visualisation
* `docs/STRUCTURAL_GRAPH_EXTRACTION.md` — structural extraction implementation details
* `docs/SERVICE_GRAPH_GENERATION.md` — service grouping and deterministic service graph derivation
* `docs/RECOMMENDATION_REPORTING.md` — report input/output artifacts, prompts, observability, and CLI usage
* `docs/EVALUATION.md` — evaluation datasets, metrics, artifacts, and cost tracking
* `docs/GRAPH_SCHEMA.md` — structural graph schema guidance
* `docs/ENGINEERING_CONVENTIONS.md` — logging, errors, typing, and validation rules
* `docs/RESPONSIBLE_AI.md` — LLM guardrails and review constraints
* `docs/PRD.md` — product framing and roadmap

## Current one-line summary

Today, Pathfinder turns a repository into a grounded service graph, evaluates likely attack movement, and produces a selected-path recommendation report and dashboard while keeping file-level structural evidence authoritative.
