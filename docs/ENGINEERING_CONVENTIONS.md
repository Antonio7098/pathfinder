# Engineering Conventions

## Purpose

This document describes the current engineering conventions used in Pathfinder for:

* structured logging
* explicit error taxonomy
* typing and schema design

These conventions are already reflected in the current implementation and should be treated as the default for future work.

Related code:

* `pathfinder/observability/logging.py`
* `pathfinder/errors.py`
* `pathfinder/structural/models.py`
* `pathfinder/adapters/codegraph_models.py`

---

## Structured logging

Pathfinder uses **structured JSON logging** rather than free-form log strings.

Current implementation entrypoint:

* `pathfinder.observability.logging.log_event(...)`

### Current logging shape

Each log record is emitted as a JSON object with at least:

* `event`

And usually additional fields such as:

* `repo_path`
* `output_path`
* `duration_seconds`
* `file_count`
* `structural_edge_count`
* `graph_path`
* `port`
* `template_version`
* `prompt_version`
* `system_prompt_sha256`
* `user_prompt_sha256`
* `model`
* `provider_request_id`
* token-usage counters when available

### Why structured logs

This supports the Pathfinder requirements that outputs remain:

* inspectable
* reconcilable with serialized artifacts
* easy to debug during extraction and serving

### Logging rules

Prefer logs that describe a meaningful lifecycle event, for example:

* `structural_extraction.started`
* `codegraph.build.completed`
* `structural_graph.projected`
* `llm.request.started`
* `llm.request.prompt`
* `llm.request.completed`
* `service_grouping.started`
* `service_grouping.completed`
* `service_graph.completed`
* `recommendation_report.completed`

Guidelines:

* always use a stable `event` name
* prefer machine-readable fields over prose
* include counts and durations when available
* include file, graph, repository, or port context when relevant
* keep logs factual; do not hide dropped or omitted data
* for LLM-backed phases, log prompt/template versions, provider/model identity, prompt hashes, and rendered prompts at debug level
* never log secrets such as API keys

### Example usage

Use the helper rather than hand-formatting JSON:

<augment_code_snippet path="pathfinder/observability/logging.py" mode="EXCERPT">
````python
def log_event(logger, event, *, level=logging.INFO, fields=None):
    payload = {"event": event}
    if fields:
        payload.update(fields)
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))
````
</augment_code_snippet>

---

## Error taxonomy

Pathfinder uses a typed exception hierarchy rooted at `PathfinderError`.

Current implementation file:

* `pathfinder/errors.py`

### Current categories

The current error categories are:

* `configuration_error`
* `repository_access_error`
* `extraction_error`
* `projection_error`
* `validation_error`
* `persistence_error`
* `internal_invariant_violation`

### Current exception classes

These map to explicit exception types:

* `ConfigurationError`
* `RepositoryAccessError`
* `ExtractionError`
* `ProjectionError`
* `ValidationError`
* `PersistenceError`
* `InternalInvariantError`

### Error design rules

Errors should:

* fail fast on correctness problems
* carry a stable category
* include actionable context as structured fields
* preserve the difference between configuration, extraction, projection, and validation failures

Helpful context often includes:

* `repo_path`
* `graph_path`
* `edge_id`
* `source`
* `target`
* upstream `cause`

### Example usage

<augment_code_snippet path="pathfinder/errors.py" mode="EXCERPT">
````python
class ProjectionError(PathfinderError):
    def __init__(self, message, *, context=None):
        super().__init__(message, category=ErrorCategory.PROJECTION, context=context)
````
</augment_code_snippet>

### When to use which category

Use:

* `ConfigurationError` for invalid inputs, missing runtime pieces, or bad CLI/runtime setup
* `RepositoryAccessError` for missing/inaccessible repositories or filesystem access problems
* `ExtractionError` for failures while invoking or reading the extractor runtime
* `ProjectionError` for failures while mapping extractor output into Pathfinder graph semantics
* `ValidationError` for schema/invariant violations in Pathfinder artifacts
* `PersistenceError` for read/write/serialization failures
* `ExternalDependencyError` for provider/runtime failures such as LLM transport or missing SDK/runtime integrations
* `InternalInvariantError` when the program reaches contradictory internal state that should never happen

---

## Typing and schema conventions

Pathfinder prefers strong typing throughout the codebase.

### Current typing approach

The current implementation uses:

* explicit function signatures
* `Path` for filesystem paths where appropriate
* enums for constrained graph categories
* Pydantic models for persisted and boundary-facing data
* immutable (`frozen=True`) models for structural artifacts

Representative files:

* `pathfinder/structural/models.py`
* `pathfinder/adapters/codegraph_models.py`

### Typing rules

Prefer:

* concrete types over `dict[str, object]` when a stable schema exists
* Pydantic models at boundaries and persisted artifact surfaces
* enums/literals for constrained categories like node and edge types
* explicit optionality via `T | None`
* typed collections such as `list[str]` and `dict[str, int]`

Avoid:

* `Any` unless it is a narrow unavoidable boundary
* passing raw unvalidated dictionaries through core logic
* hidden schema assumptions in helper functions

### Boundary model examples

Pathfinder already treats both extractor input and artifact output as typed schemas.

Examples:

* raw CodeGraph document models in `pathfinder/adapters/codegraph_models.py`
* structural graph artifact models in `pathfinder/structural/models.py`
* service grouping and service graph models in `pathfinder/services/models.py`
* recommendation report input/output models in `pathfinder/reporting/input_models.py` and `pathfinder/reporting/models.py`
* reusable LLM boundary models in `pathfinder/llm/models.py`

### Invariant validation

Typing is not only static annotation; it is also runtime validation at trust boundaries.

For example, the structural artifact validates that:

* file node ids are unique
* structural edges reference existing file nodes
* summary counts match serialized node/edge counts

This is why schema models should remain close to persisted artifacts and cross-phase boundaries.

---

## Practical guidance for future changes

When adding a new subsystem or artifact:

1. define the boundary model first
2. prefer an explicit error category before adding fallback behavior
3. emit structured lifecycle logs with counts/context
4. validate invariants at the boundary
5. keep internal transformations typed and small

If a new feature cannot be explained through its logs, typed models, and explicit failure modes, it is probably not ready.