# Agent Instructions: Code Review Against the VS Rubric

## Purpose

Use this guide when an agent is asked to review a Pathfinder phase, deliverable, or branch against the VS rubric stored in:

- `ops/VS-rubric - Sheet1.csv`

The goal is not just to give scores. The goal is to produce a **defensible review** that:

- maps the work to the rubric faithfully
- cites concrete evidence from the repo
- distinguishes shipped reality from future aspiration
- records caveats and scope limitations clearly

## Review principles

The review must follow `AGENTS.md` and the project principles.

In particular:

- be evidence-led, not vibe-led
- fail fast on unsupported claims
- prefer explicit citations over broad praise
- distinguish implementation quality from presentation quality
- do not award points for work that was merely planned
- do not penalize out-of-scope categories without naming the scope constraint

## Inputs the reviewer must inspect

Before scoring, inspect at minimum:

- the relevant implementation files
- tests and validation outputs
- the phase report in `ops/reports/` if present
- the plan doc in `ops/` if present
- the rubric CSV itself
- git state or PR context if relevant

If the review concerns a completed phase, inspect both:

- what was built
- how it was validated

## Required review workflow

### 1. Define scope first

State clearly:

- what artifact or phase is being reviewed
- what branch/PR/release it corresponds to
- what was intentionally in scope
- what was intentionally out of scope

### 2. Extract rubric criteria faithfully

For each rubric row:

- preserve the original criterion name
- preserve the original option wording where practical
- note whether the row is a 3-level or 4-level rubric

Do not silently normalize away important differences in the rubric.

### 3. Score only from evidence

Every score must be backed by concrete evidence such as:

- specific files
- specific tests
- specific execution results
- specific reports or docs

If evidence is weak, lower confidence or mark the item as provisional.

### 4. Separate missing scope from weak performance

If a criterion was not meaningfully in scope, say so explicitly.

Examples:

- demo criteria may be `Not assessed in this phase` if no demo was created
- deployment robustness should not be overclaimed for a non-deployed internal phase

### 5. Record strengths, weaknesses, and next actions

Every completed review should include:

- top strengths
- top weaknesses or risks
- recommended next actions

## Scoring guidance

### Solution quality rows

For rows like:

- `Solution - Creation`
- `Solution - Implementation`
- `Solution - Effectiveness`

Choose the **closest exact rubric band** and quote that band in the review.

### Yes / Somewhat / No rows

For rows like:

- `Is it cost efficient?`
- `Is it scalable?`
- `Does it practice responsible use of AI?`

Pick one of:

- `Yes - Intentional design`
- `Somewhat - Tangential effect`
- `Not at all`

Do not upgrade a score to `Yes` unless the evidence shows intentional design choices.

### Report and demo rows

For report/demo criteria:

- assess only the artifacts that actually exist
- if no artifact exists, mark `Not assessed in this phase`
- if an artifact exists but is weak, score it honestly rather than deferring

## Required output structure

Use the template in:

- `ops/reviews/templates/vs-rubric-review-template.md`

At minimum the review output must include:

1. review scope
2. evidence base
3. scorecard table
4. detailed rationale
5. strengths
6. weaknesses / caveats
7. recommended next iteration
8. reviewer confidence

## Evidence standards

Good evidence:

- `tests/test_structural_graph.py` passed with `8 passed`
- `pathfinder/structural/projector.py` preserves provenance and diagnostics
- `ops/reports/structural-graph-extraction-execution-report.md` records cross-repo validation

Weak evidence:

- "the architecture seems scalable"
- "the code feels enterprise"
- "it should be easy to extend"

## Tone guidance

Write the review like a serious internal evaluator:

- concise but specific
- fair but not flattering by default
- willing to credit strong engineering
- willing to call out missing demo/sellability/presentation work

## Output location conventions

Store completed reviews under:

- `ops/reviews/`

Use filenames like:

- `ops/reviews/<phase-or-branch>-vs-rubric-review.md`

Store reusable forms under:

- `ops/reviews/templates/`