"""CLI entrypoint for Pathfinder structural extraction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pathfinder.errors import PathfinderError
from pathfinder.observability.logging import configure_logging, get_logger
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)
    logger = get_logger("pathfinder")

    if args.command != "build-structural-graph":
        parser.error(f"Unsupported command: {args.command}")

    service = StructuralExtractionService(logger)
    request = StructuralExtractionRequest(
        repo_path=args.repo,
        output_path=args.output,
        raw_codegraph_output_path=args.raw_codegraph_output,
        include_hidden=args.include_hidden,
        continue_on_parse_error=not args.strict_parse,
    )
    try:
        result = service.run(request)
    except PathfinderError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result.artifact.summary.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
