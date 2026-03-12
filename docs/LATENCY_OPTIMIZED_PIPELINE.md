# Latency Optimized Pipeline

This document describes the latency-optimized Pathfinder pipeline variant, how to run it, and the latency gains measured against the demo fixture.

## Goal

The standard full pipeline remains available and unchanged:

* `python -m pathfinder.cli run-full-pipeline`

The latency-optimized variant is a separate command:

* `python -m pathfinder.cli run-latency-optimized-pipeline`

This preserves the original pipeline while providing a faster option for LLM-heavy runs.

## What changed

The latency-optimized pipeline keeps the same phase boundaries and artifacts:

* structural extraction
* service grouping
* service graph construction
* security evaluation
* path selection
* recommendation generation
* dashboard rendering

The main difference is inside security evaluation:

* node and edge analysis use bounded fan-out instead of the more conservative serialized behavior
* concurrency is limited with a semaphore via `--max-concurrent-security-tasks`
* structured LLM calls are wrapped with retry/backoff and jitter to better tolerate transient failures and `429` rate limits

This keeps the pipeline explainable and artifact-compatible while reducing time spent in the LLM-heavy security stage.

## How to run it

Example using OpenRouter and the model used for the timing run:

```bash
python -m pathfinder.cli run-latency-optimized-pipeline \
  --repo tests/fixtures/demo_vuln_repo \
  --output-dir demo-output-latency \
  --graph-mode service \
  --provider openrouter \
  --model nvidia/nemotron-3-super-120b-a12b:free \
  --timeout-seconds 300 \
  --max-concurrent-security-tasks 6
```

The standard pipeline for comparison:

```bash
python -m pathfinder.cli run-full-pipeline \
  --repo tests/fixtures/demo_vuln_repo \
  --output-dir demo-output \
  --graph-mode service \
  --provider openrouter \
  --model nvidia/nemotron-3-super-120b-a12b:free \
  --timeout-seconds 300
```

## Measured latency gains

Fixture:

* `tests/fixtures/demo_vuln_repo`

Model:

* `nvidia/nemotron-3-super-120b-a12b:free`

Observed wall-clock timings on March 12, 2026:

* standard pipeline with `--timeout-seconds 120`: failed after `176.28s` because `evaluate_security` timed out
* standard pipeline with `--timeout-seconds 300`: completed in `344.59s`
* latency-optimized pipeline with `--timeout-seconds 300`: completed in `238.67s`

Measured improvement versus the successful standard run:

* `105.92s` faster
* about `30.7%` lower end-to-end latency

## Notes

The largest remaining source of runtime variance is provider-side latency in:

* service grouping
* security evaluation
* recommendation generation

The retry wrapper improves resilience under transient failures, but it does not eliminate provider variance. For larger repositories, tune:

* `--timeout-seconds`
* `--max-concurrent-security-tasks`

Start conservatively if the provider is rate limiting heavily, then increase concurrency gradually.
