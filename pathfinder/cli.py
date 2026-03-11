"""CLI entrypoint for Pathfinder structural extraction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pathfinder.errors import PathfinderError
from pathfinder.observability.logging import configure_logging, get_logger
from pathfinder.reporting.enums import GraphScope
from pathfinder.reporting.input_builder import RecommendationInputBuildRequest, RecommendationInputBuilderService
from pathfinder.reporting.service import RecommendationReportRequest, create_openrouter_recommendation_report_service
from pathfinder.services.service import ServiceGraphRequest, ServiceGraphService, ServiceGroupingRequest, create_openrouter_service_grouping_service
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

    report_input = subparsers.add_parser("build-recommendation-input", help="Build a recommendation report input artifact from either a file graph path or a service graph path")
    report_input.add_argument("--graph-scope", choices=[scope.value for scope in GraphScope], default=GraphScope.FILE.value, help="Graph scope to use when resolving path nodes")
    report_input.add_argument("--structural-graph", type=Path, required=True, help="Structural graph artifact JSON")
    report_input.add_argument("--service-graph", type=Path, default=None, help="Service graph artifact JSON, required for service scope")
    report_input.add_argument("--grouping", type=Path, default=None, help="Service grouping artifact JSON, required for service scope")
    report_input.add_argument("--path-node-id", action="append", dest="path_node_ids", required=True, help="Ordered path node id; repeat for each node in the path")
    report_input.add_argument("--focal-file", action="append", dest="focal_file_paths", default=None, help="Extra grounded file to include in report context")
    report_input.add_argument("--path-id", default="selected-path", help="Stable path identifier")
    report_input.add_argument("--input-artifact-id", default=None, help="Optional explicit input artifact identifier")
    report_input.add_argument("--output", type=Path, default=Path("recommendation_input.json"), help="Output path for recommendation input JSON")
    report_input.add_argument("--verbose", action="store_true", help="Enable debug logging")

    report = subparsers.add_parser("generate-recommendation-report", help="Generate a grounded mitigation report from a selected path input artifact")
    report.add_argument("--input", type=Path, required=True, help="Recommendation report input artifact JSON")
    report.add_argument("--output", type=Path, default=Path("recommendation_report.json"), help="Output path for recommendation report JSON")
    report.add_argument("--template-version", default="recommendation-report-v1", help="Recommendation prompt template version")
    report.add_argument("--model", default=None, help="Optional OpenRouter model override")
    report.add_argument("--max-files", type=int, default=8, help="Maximum number of repository files to include in prompt context")
    report.add_argument("--max-file-chars", type=int, default=4000, help="Maximum characters to include per file")
    report.add_argument("--timeout-seconds", type=float, default=60.0, help="Per-request LLM timeout in seconds")
    report.add_argument("--verbose", action="store_true", help="Enable debug logging")

    grouping = subparsers.add_parser("identify-services", help="Infer a grounded service grouping overlay from a structural graph artifact")
    grouping.add_argument("--input", type=Path, required=True, help="Structural graph artifact JSON")
    grouping.add_argument("--output", type=Path, default=Path("service_grouping.json"), help="Output path for service grouping JSON")
    grouping.add_argument("--raw-codegraph", type=Path, default=None, help="Optional raw CodeGraph artifact JSON for richer graphcode context")
    grouping.add_argument("--template-version", default="service-grouping-v1", help="Service grouping prompt template version")
    grouping.add_argument("--model", default=None, help="Optional OpenRouter model override")
    grouping.add_argument("--timeout-seconds", type=float, default=60.0, help="Per-request LLM timeout in seconds")
    grouping.add_argument("--max-output-tokens", type=int, default=8192, help="Maximum completion tokens for the service-grouping LLM response")
    grouping.add_argument("--verbose", action="store_true", help="Enable debug logging")

    service_graph = subparsers.add_parser("build-service-graph", help="Build a derived service graph from a structural graph and service grouping artifact")
    service_graph.add_argument("--structural-graph", type=Path, required=True, help="Structural graph artifact JSON")
    service_graph.add_argument("--grouping", type=Path, required=True, help="Service grouping artifact JSON")
    service_graph.add_argument("--output", type=Path, default=Path("service_graph.json"), help="Output path for service graph JSON")
    service_graph.add_argument("--verbose", action="store_true", help="Enable debug logging")
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

        if args.command == "build-recommendation-input":
            service = RecommendationInputBuilderService(logger)
            result = service.run(
                RecommendationInputBuildRequest(
                    graph_scope=GraphScope(args.graph_scope),
                    structural_graph_path=args.structural_graph,
                    service_graph_path=args.service_graph,
                    grouping_path=args.grouping,
                    path_node_ids=args.path_node_ids,
                    focal_file_paths=args.focal_file_paths or [],
                    path_id=args.path_id,
                    input_artifact_id=args.input_artifact_id,
                    output_path=args.output,
                )
            )
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

        if args.command == "identify-services":
            service = create_openrouter_service_grouping_service(
                logger,
                model_override=args.model,
                timeout_seconds=args.timeout_seconds,
            )
            result = service.run(
                ServiceGroupingRequest(
                    input_path=args.input,
                    output_path=args.output,
                    raw_codegraph_input_path=args.raw_codegraph,
                    template_version=args.template_version,
                    timeout_seconds=args.timeout_seconds,
                    max_output_tokens=args.max_output_tokens,
                )
            )
            print(json.dumps(result.artifact.summary.model_dump(mode="json"), sort_keys=True))
            return 0

        if args.command == "build-service-graph":
            service = ServiceGraphService(logger)
            result = service.run(
                ServiceGraphRequest(
                    structural_graph_path=args.structural_graph,
                    grouping_path=args.grouping,
                    output_path=args.output,
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
