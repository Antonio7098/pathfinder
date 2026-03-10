"""CLI entrypoint for Pathfinder structural extraction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pathfinder.errors import PathfinderError
from pathfinder.observability.logging import configure_logging, get_logger
from pathfinder.reporting.service import RecommendationReportRequest, create_openrouter_recommendation_report_service
from pathfinder.structural.service import StructuralExtractionRequest, StructuralExtractionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pathfinder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-structural-graph", help="Build a structural file graph from a repository")
    build.add_argument("--repo", type=Path, required=True, help="Repository path to analyze")
    build.add_argument("--output", type=Path, default=Path("structural_graph.json"), help="Output path for structural graph JSON")
    build.add_argument("--raw-codegraph-output", type=Path, default=None, help="Optional output path for raw CodeGraph JSON")
    build.add_argument("--include-hidden", action="store_true", help="Include hidden files during extraction")
    build.add_argument("--strict-parse", action="store_true", help="Fail extraction on parse errors")
    build.add_argument("--verbose", action="store_true", help="Enable debug logging")

    report = subparsers.add_parser("generate-recommendation-report", help="Generate a grounded mitigation report from a selected path input artifact")
    report.add_argument("--input", type=Path, required=True, help="Recommendation report input artifact JSON")
    report.add_argument("--output", type=Path, default=Path("recommendation_report.json"), help="Output path for recommendation report JSON")
    report.add_argument("--template-version", default="recommendation-report-v1", help="Recommendation prompt template version")
    report.add_argument("--model", default=None, help="Optional OpenRouter model override")
    report.add_argument("--max-files", type=int, default=8, help="Maximum number of repository files to include in prompt context")
    report.add_argument("--max-file-chars", type=int, default=4000, help="Maximum characters to include per file")
    report.add_argument("--timeout-seconds", type=float, default=60.0, help="Per-request LLM timeout in seconds")
    report.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)
    logger = get_logger("pathfinder")

    try:
        if args.command == "build-structural-graph":
            service = StructuralExtractionService(logger)
            request = StructuralExtractionRequest(
                repo_path=args.repo,
                output_path=args.output,
                raw_codegraph_output_path=args.raw_codegraph_output,
                include_hidden=args.include_hidden,
                continue_on_parse_error=not args.strict_parse,
            )
            result = service.run(request)
            print(json.dumps(result.artifact.summary.model_dump(mode="json"), sort_keys=True))
            return 0

        if args.command == "generate-recommendation-report":
            service = create_openrouter_recommendation_report_service(
                logger,
                model_override=args.model,
                timeout_seconds=args.timeout_seconds,
            )
            result = service.run(
                RecommendationReportRequest(
                    input_path=args.input,
                    output_path=args.output,
                    template_version=args.template_version,
                    max_files=args.max_files,
                    max_file_chars=args.max_file_chars,
                    timeout_seconds=args.timeout_seconds,
                )
            )
            print(json.dumps(result.artifact.summary.model_dump(mode="json"), sort_keys=True))
            return 0

        parser.error(f"Unsupported command: {args.command}")
    except PathfinderError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
