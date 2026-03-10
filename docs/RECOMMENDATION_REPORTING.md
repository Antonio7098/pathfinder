# Recommendation Reporting

## Purpose

Pathfinder now includes a **post-path recommendation reporting layer**.

This layer is intentionally separate from:

1. structural extraction
2. attack-edge derivation
3. deterministic path search

It starts **after** an upstream phase has already selected a path.

## Implemented modules

* `pathfinder/llm/` — reusable provider-agnostic structured LLM interface and the OpenRouter/OpenAI SDK adapter
* `pathfinder/reporting/input_models.py` — versioned path/report input artifact
* `pathfinder/reporting/models.py` — versioned recommendation report artifact
* `pathfinder/reporting/templates.py` — versioned prompt templates
* `pathfinder/reporting/context.py` — deterministic file-context collection and truncation/drop diagnostics
* `pathfinder/reporting/service.py` — orchestration and CLI-facing service

## Runtime configuration

The OpenRouter integration reads configuration from environment variables, with `.env` support:

* `OPENROUTER_API_KEY`
* `OPENROUTER_MODEL_ID`
* optional `OPENROUTER_BASE_URL`
* optional `OPENROUTER_APP_NAME`

The transport uses the **OpenAI SDK** with `base_url=https://openrouter.ai/api/v1` behind a reusable interface.

## CLI

Generate a report from a path input artifact:

* `python -m pathfinder.cli generate-recommendation-report --input recommendation_input.json --output recommendation_report.json`

Useful options:

* `--model` to override the configured OpenRouter model
* `--max-files` to cap prompt context breadth
* `--max-file-chars` to cap per-file prompt payload size
* `--timeout-seconds` to control provider timeout
* `--verbose` to emit debug-level prompt logs

## Input artifact

`RecommendationReportInputArtifact` is the phase boundary for report generation.

It includes:

* `input_artifact_id`
* `version`
* `repo_path`
* `path_id`
* ordered `path_nodes`
* ordered `path_edges`
* `focal_files`
* `summary`

Validation rules include:

* path node ids are unique
* path edge ids are unique
* path edges align with the ordered node sequence
* summary counts reconcile with serialized content

## Report artifact

`RecommendationReportArtifact` persists:

* `report_id`
* `version`
* `template_version`
* `input_artifact_id`
* `known_file_paths`
* `path_overview`
* structured `recommendations`
* `llm_invocation`
* `summary`
* `diagnostics`

The report artifact validates that:

* cited file paths are grounded in known input files
* cited node ids and edge ids exist on the supplied path
* summary counts reconcile with serialized recommendations and citations

## Observability

The reporting flow is designed for high observability.

Structured logs include lifecycle events such as:

* `recommendation_report.started`
* `recommendation_report.context.built`
* `llm.request.started`
* `llm.request.prompt`
* `llm.request.completed`
* `recommendation_report.completed`

Captured audit fields include:

* provider and model
* template version and prompt version
* rendered prompt bodies
* prompt SHA-256 hashes
* provider request id
* token usage when returned
* durations
* file-context truncation, missing-file, and dropped-file counts

Secrets such as API keys must never be logged.

## Reuse story

The `pathfinder.llm` package is intended to be reused by future Pathfinder phases, including:

* per-file target/risk analysis
* per-structural-edge attack-edge derivation
* future explanation layers that still need bounded, schema-constrained LLM calls

The key reusable contracts are:

* `StructuredLLMClient`
* `StructuredLLMRequest`
* `StructuredPrompt`
* `LLMInvocationRecord`

## Testing

Current tests cover:

* OpenAI/OpenRouter adapter request translation and response parsing
* input/report artifact invariant validation
* context building, truncation, and dropped-file accounting
* report service orchestration and persisted artifact generation
* CLI wiring for the new report command