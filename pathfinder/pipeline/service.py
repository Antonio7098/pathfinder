"""Stageflow-backed end-to-end Pathfinder pipeline."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from dataclasses import asdict
from pathlib import Path

from stageflow.api import Pipeline, StageContext, StageKind, stage_metadata
from stageflow.pipeline.interceptors import LoggingInterceptor, MetricsInterceptor, TimeoutInterceptor

from pathfinder.errors import ValidationError
from pathfinder.observability.logging import log_event
from pathfinder.pipeline.models import FullPipelineRequest, FullPipelineResult
from pathfinder.reporting.input_models import PathEdgeInput, PathNodeInput, RecommendationReportInputArtifact, RecommendationReportInputSummary, ReportFileReference
from pathfinder.reporting.service import (
    RecommendationReportRequest,
    create_minimax_recommendation_report_service,
    create_openrouter_recommendation_report_service,
)
from pathfinder.security_evaluators.security_tools import AttackGraphOrchestrator, PathfinderAI
from pathfinder.services.io import read_service_graph
from pathfinder.services.service import (
    ServiceGraphRequest,
    ServiceGraphService,
    ServiceGroupingRequest,
    create_minimax_service_grouping_service,
    create_openrouter_service_grouping_service,
)
from pathfinder.structural.io import read_structural_graph
from pathfinder.structural.service import StructuralExtractionRequest, StructuralExtractionService


def _stage_data(ctx: StageContext, stage_name: str) -> dict:
    output = ctx.inputs.get_output(stage_name)
    return {} if output is None or output.data is None else dict(output.data)


@stage_metadata(name="build_structural_graph", kind=StageKind.WORK)
class BuildStructuralGraphStage:
    async def execute(self, ctx: StageContext) -> dict[str, str]:
        request: FullPipelineRequest = ctx.snapshot.metadata["request"]
        logger = ctx.snapshot.metadata["logger"]
        service = StructuralExtractionService(logger)
        output_dir = request.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        result = await asyncio.to_thread(
            service.run,
            StructuralExtractionRequest(
                repo_path=request.repo_path,
                output_path=output_dir / "structural_graph.json",
                raw_codegraph_output_path=output_dir / "raw_codegraph.json",
                include_hidden=request.include_hidden,
                continue_on_parse_error=not request.strict_parse,
            ),
        )
        return {
            "structural_graph_path": str(result.output_path),
            "raw_codegraph_path": str(result.raw_codegraph_output_path),
        }


@stage_metadata(name="identify_services", kind=StageKind.ENRICH)
class IdentifyServicesStage:
    async def execute(self, ctx: StageContext) -> dict[str, str]:
        request: FullPipelineRequest = ctx.snapshot.metadata["request"]
        logger = ctx.snapshot.metadata["logger"]
        build_data = _stage_data(ctx, "build_structural_graph")
        if request.provider == "minimax":
            service = create_minimax_service_grouping_service(logger, model_override=request.model, timeout_seconds=request.timeout_seconds)
        else:
            service = create_openrouter_service_grouping_service(logger, model_override=request.model, timeout_seconds=request.timeout_seconds)
        result = await asyncio.to_thread(
            service.run,
            ServiceGroupingRequest(
                input_path=Path(build_data["structural_graph_path"]),
                raw_codegraph_input_path=Path(build_data["raw_codegraph_path"]),
                output_path=request.output_dir / "service_grouping.json",
                timeout_seconds=request.timeout_seconds,
                max_output_tokens=request.max_output_tokens,
            ),
        )
        return {"service_grouping_path": str(result.output_path)}


@stage_metadata(name="build_service_graph", kind=StageKind.WORK)
class BuildServiceGraphStage:
    async def execute(self, ctx: StageContext) -> dict[str, str]:
        request: FullPipelineRequest = ctx.snapshot.metadata["request"]
        logger = ctx.snapshot.metadata["logger"]
        build_data = _stage_data(ctx, "build_structural_graph")
        grouping_data = _stage_data(ctx, "identify_services")
        service = ServiceGraphService(logger)
        result = await asyncio.to_thread(
            service.run,
            ServiceGraphRequest(
                structural_graph_path=Path(build_data["structural_graph_path"]),
                grouping_path=Path(grouping_data["service_grouping_path"]),
                output_path=request.output_dir / "service_graph.json",
            ),
        )
        return {"service_graph_path": str(result.output_path)}


@stage_metadata(name="evaluate_security", kind=StageKind.ENRICH)
class EvaluateSecurityStage:
    async def execute(self, ctx: StageContext) -> dict[str, str]:
        request: FullPipelineRequest = ctx.snapshot.metadata["request"]
        logger = ctx.snapshot.metadata["logger"]
        if request.provider == "minimax":
            ai = PathfinderAI(model=request.model, provider=request.provider, logger=logger)
        else:
            ai = PathfinderAI(model=request.model, logger=logger)
        if request.graph_mode == "service":
            service_graph_data = _stage_data(ctx, "build_service_graph")
            graph_input = await asyncio.to_thread(
                _build_service_security_graph_input,
                repo_path=request.repo_path,
                service_graph_path=Path(service_graph_data["service_graph_path"]),
            )
        else:
            build_data = _stage_data(ctx, "build_structural_graph")
            artifact = read_structural_graph(Path(build_data["structural_graph_path"]))
            orchestrator = AttackGraphOrchestrator(request.repo_path, ai=ai)
            graph_input = await asyncio.to_thread(
                _build_file_security_graph_input,
                artifact=artifact,
                repo_path=request.repo_path,
            )
        graph = await _run_security_subpipeline(
            graph_input=graph_input,
            ai=ai,
            timeout_seconds=request.timeout_seconds,
            provider=request.provider,
        )
        output_path = request.output_dir / "security_graph.json"
        output_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"security_graph_path": str(output_path)}


@stage_metadata(name="select_attack_path", kind=StageKind.GUARD)
class SelectAttackPathStage:
    async def execute(self, ctx: StageContext) -> dict[str, object]:
        security_data = _stage_data(ctx, "evaluate_security")
        security_graph = json.loads(Path(security_data["security_graph_path"]).read_text(encoding="utf-8"))
        selected_path = _select_best_path(security_graph)
        return selected_path


@stage_metadata(name="build_report_input", kind=StageKind.TRANSFORM)
class BuildReportInputStage:
    async def execute(self, ctx: StageContext) -> dict[str, str]:
        request: FullPipelineRequest = ctx.snapshot.metadata["request"]
        security_data = _stage_data(ctx, "evaluate_security")
        selected_path = _stage_data(ctx, "select_attack_path")
        security_graph = json.loads(Path(security_data["security_graph_path"]).read_text(encoding="utf-8"))
        report_input = _build_report_input_artifact(
            repo_path=request.repo_path,
            security_graph=security_graph,
            selected_path=selected_path,
        )
        output_path = request.output_dir / "recommendation_input.json"
        output_path.write_text(json.dumps(report_input.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"recommendation_input_path": str(output_path)}


@stage_metadata(name="generate_recommendations", kind=StageKind.AGENT)
class GenerateRecommendationsStage:
    async def execute(self, ctx: StageContext) -> dict[str, str]:
        request: FullPipelineRequest = ctx.snapshot.metadata["request"]
        logger = ctx.snapshot.metadata["logger"]
        report_input_data = _stage_data(ctx, "build_report_input")
        if request.provider == "minimax":
            service = create_minimax_recommendation_report_service(logger, model_override=request.model, timeout_seconds=request.timeout_seconds)
        else:
            service = create_openrouter_recommendation_report_service(logger, model_override=request.model, timeout_seconds=request.timeout_seconds)
        result = await asyncio.to_thread(
            service.run,
            RecommendationReportRequest(
                input_path=Path(report_input_data["recommendation_input_path"]),
                output_path=request.output_dir / "recommendation_report.json",
                max_files=request.max_files,
                max_file_chars=request.max_file_chars,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        return {"recommendation_report_path": str(result.output_path)}


@stage_metadata(name="render_dashboard", kind=StageKind.WORK)
class RenderDashboardStage:
    async def execute(self, ctx: StageContext) -> dict[str, str]:
        request: FullPipelineRequest = ctx.snapshot.metadata["request"]
        security_data = _stage_data(ctx, "evaluate_security")
        selected_path = _stage_data(ctx, "select_attack_path")
        recommendation_data = _stage_data(ctx, "generate_recommendations")
        from pathfinder.reporting.io import read_recommendation_report

        security_graph = json.loads(Path(security_data["security_graph_path"]).read_text(encoding="utf-8"))
        report = read_recommendation_report(Path(recommendation_data["recommendation_report_path"]))
        output_path = request.output_dir / "dashboard.html"
        await asyncio.to_thread(
            _render_dashboard_html,
            graph_mode=request.graph_mode,
            security_graph=security_graph,
            selected_path=selected_path,
            recommendation_report=report,
            output_path=output_path,
        )
        return {"dashboard_path": str(output_path)}


class FullPipelineService:
    def __init__(self, logger) -> None:
        self._logger = logger

    async def run(self, request: FullPipelineRequest) -> FullPipelineResult:
        TimeoutInterceptor.DEFAULT_TIMEOUT_MS = max(int(request.timeout_seconds * 1000), 1)
        pipeline = (
            Pipeline()
            .with_stage("build_structural_graph", BuildStructuralGraphStage, StageKind.WORK)
            .with_stage("identify_services", IdentifyServicesStage, StageKind.ENRICH, dependencies=("build_structural_graph",))
            .with_stage("build_service_graph", BuildServiceGraphStage, StageKind.WORK, dependencies=("build_structural_graph", "identify_services"))
            .with_stage("evaluate_security", EvaluateSecurityStage, StageKind.ENRICH, dependencies=("build_structural_graph", "build_service_graph"))
            .with_stage("select_attack_path", SelectAttackPathStage, StageKind.GUARD, dependencies=("evaluate_security",))
            .with_stage("build_report_input", BuildReportInputStage, StageKind.TRANSFORM, dependencies=("evaluate_security", "select_attack_path"))
            .with_stage("generate_recommendations", GenerateRecommendationsStage, StageKind.AGENT, dependencies=("build_report_input",))
            .with_stage("render_dashboard", RenderDashboardStage, StageKind.WORK, dependencies=("evaluate_security", "select_attack_path", "generate_recommendations"))
        )
        log_event(
            self._logger,
            "full_pipeline.started",
            fields={"repo_path": str(request.repo_path), "output_dir": str(request.output_dir)},
        )
        results = await pipeline.run(
            interceptors=[LoggingInterceptor(), MetricsInterceptor()],
            emit_stage_wide_events=False,
            emit_pipeline_wide_event=False,
            metadata={"request": request, "logger": self._logger},
            input_text=str(request.repo_path),
            topology="pathfinder_full_pipeline",
            execution_mode="default",
        )
        failed_stages = results.failed()
        if failed_stages:
            raise ValidationError("Full pipeline failed", context={"failed_stages": failed_stages})
        structural_data = results.data("build_structural_graph")
        grouping_data = results.data("identify_services")
        service_graph_data = results.data("build_service_graph")
        security_data = results.data("evaluate_security")
        report_input_data = results.data("build_report_input")
        recommendation_data = results.data("generate_recommendations")
        dashboard_data = results.data("render_dashboard")
        result = FullPipelineResult(
            structural_graph_path=Path(structural_data["structural_graph_path"]),
            raw_codegraph_path=Path(structural_data["raw_codegraph_path"]),
            service_grouping_path=Path(grouping_data["service_grouping_path"]),
            service_graph_path=Path(service_graph_data["service_graph_path"]),
            security_graph_path=Path(security_data["security_graph_path"]),
            selected_path_input_path=Path(report_input_data["recommendation_input_path"]),
            recommendation_report_path=Path(recommendation_data["recommendation_report_path"]),
            dashboard_path=Path(dashboard_data["dashboard_path"]),
        )
        log_event(
            self._logger,
            "full_pipeline.completed",
            fields={key: str(value) for key, value in asdict(result).items()},
        )
        return result


def _select_best_path(security_graph: dict[str, object]) -> dict[str, object]:
    nodes = {node["id"]: node for node in security_graph["nodes"]}
    edges_by_source: dict[str, list[dict[str, object]]] = {}
    for raw_edge in security_graph["attack_edges"]:
        edge = dict(raw_edge)
        edge["edge_score"] = round(
            (edge["edge_attack_cost"] * 2)
            + (edge["detection_risk"] * 3)
            + (1 - edge["transition_likelihood"])
            - _node_reward(nodes[edge["target"]]),
            6,
        )
        edges_by_source.setdefault(edge["source"], []).append(edge)

    for source_edges in edges_by_source.values():
        source_edges.sort(key=lambda item: (item["target"], item["attack_type"], item["id"]))

    entry_nodes = sorted(node_id for node_id, node in nodes.items() if node.get("entrypoint_flag"))
    target_nodes = set(node_id for node_id, node in nodes.items() if node.get("target_flag"))
    best: tuple[float, list[str], list[str]] | None = None
    best_partial: tuple[float, list[str], list[str]] | None = None

    def visit(current: str, node_path: list[str], edge_path: list[str], score: float, seen: set[str]) -> None:
        nonlocal best, best_partial
        if edge_path:
            candidate_partial = (round(score, 6), list(node_path), list(edge_path))
            if best_partial is None or candidate_partial < best_partial:
                best_partial = candidate_partial
        if current in target_nodes and edge_path:
            candidate = (round(score, 6), list(node_path), list(edge_path))
            if best is None or candidate < best:
                best = candidate
        for edge in edges_by_source.get(current, []):
            if edge["target"] in seen:
                continue
            visit(
                edge["target"],
                node_path + [edge["target"]],
                edge_path + [edge["id"]],
                score + edge["edge_score"],
                seen | {edge["target"]},
            )

    for entry in entry_nodes:
        visit(entry, [entry], [], 0.0, {entry})

    if best is None:
        if best_partial is None:
            raise ValidationError(
                "No attack path connects an entry file to a target file",
                context={"entry_node_count": len(entry_nodes), "target_node_count": len(target_nodes)},
            )
        best = best_partial

    selected_edges = []
    attack_edges_by_id = {edge["id"]: edge for edge in security_graph["attack_edges"]}
    for edge_id in best[2]:
        edge = dict(attack_edges_by_id[edge_id])
        edge["edge_score"] = round(
            (edge["edge_attack_cost"] * 2)
            + (edge["detection_risk"] * 3)
            + (1 - edge["transition_likelihood"])
            - _node_reward(nodes[edge["target"]]),
            6,
        )
        selected_edges.append(edge)
    return {"score": best[0], "nodes": best[1], "edges": best[2], "edge_details": selected_edges}


def _node_reward(node: dict[str, object]) -> float:
    if node.get("target_flag"):
        return (node.get("security_scores", {}).get("data_access_value", 0.0) * 5) + (node.get("security_scores", {}).get("privilege_gain", 0.0) * 2)
    if node.get("entrypoint_flag"):
        return node.get("security_scores", {}).get("exploitability", 0.0) * 3
    return node.get("security_scores", {}).get("lateral_movement_value", 0.0)


def _build_report_input_artifact(*, repo_path: Path, security_graph: dict[str, object], selected_path: dict[str, object]) -> RecommendationReportInputArtifact:
    nodes_by_id = {node["id"]: node for node in security_graph["nodes"]}
    attack_edges_by_id = {edge["id"]: edge for edge in security_graph["attack_edges"]}
    path_nodes = [
        PathNodeInput(
            id=node_id,
            path=nodes_by_id[node_id]["path"],
            language=nodes_by_id[node_id].get("language") or _infer_language(nodes_by_id[node_id]["path"]),
            role=_node_role(nodes_by_id[node_id]),
            target_flag=nodes_by_id[node_id].get("target_flag", False),
            normalized_risk_score=nodes_by_id[node_id].get("normalized_risk_score"),
            confidence=nodes_by_id[node_id].get("confidence"),
            rationale=nodes_by_id[node_id].get("rationale"),
        )
        for node_id in selected_path["nodes"]
    ]
    path_edges = [
        PathEdgeInput(
            id=edge_id,
            source=attack_edges_by_id[edge_id]["source"],
            target=attack_edges_by_id[edge_id]["target"],
            attack_type=attack_edges_by_id[edge_id]["attack_type"],
            edge_attack_cost=attack_edges_by_id[edge_id]["edge_attack_cost"],
            confidence=attack_edges_by_id[edge_id]["confidence"],
            rationale=attack_edges_by_id[edge_id]["rationale"],
            structural_basis_edge_ids=attack_edges_by_id[edge_id].get("structural_basis_edge_ids", []),
        )
        for edge_id in selected_path["edges"]
    ]
    focal_files = [ReportFileReference(path=node.path, reason="selected_attack_path") for node in path_nodes]
    for node_id in selected_path["nodes"]:
        for extra_path in nodes_by_id[node_id].get("focal_file_paths", []):
            if extra_path not in {item.path for item in focal_files}:
                focal_files.append(ReportFileReference(path=extra_path, reason="graph_node_membership"))
    return RecommendationReportInputArtifact(
        input_artifact_id=f"input:{repo_path.name}:{selected_path['nodes'][0]}:{selected_path['nodes'][-1]}",
        repo_path=str(repo_path),
        graph_id=security_graph.get("graph_id"),
        path_id=f"path:{selected_path['nodes'][0]}->{selected_path['nodes'][-1]}",
        path_nodes=path_nodes,
        path_edges=path_edges,
        focal_files=focal_files,
        summary=RecommendationReportInputSummary(
            path_node_count=len(path_nodes),
            path_edge_count=len(path_edges),
            focal_file_count=len(focal_files),
        ),
    )


def _render_dashboard_html(*, graph_mode: str, security_graph: dict[str, object], selected_path: dict[str, object], recommendation_report, output_path: Path) -> None:
    report_html = _recommendation_report_html(recommendation_report)
    try:
        if graph_mode == "service":
            dashboard = _build_service_dashboard(security_graph=security_graph, selected_path=selected_path)
        else:
            dashboard = _build_file_dashboard(security_graph=security_graph, selected_path=selected_path)
        dashboard.export_html(str(output_path), report_html=report_html)
    except ModuleNotFoundError as exc:
        if exc.name not in {"networkx", "pyvis", "vis-network"}:
            raise
        output_path.write_text(_build_dashboard_fallback_html(selected_path=selected_path, report_html=report_html), encoding="utf-8")


def _build_file_dashboard(*, security_graph: dict[str, object], selected_path: dict[str, object]) -> AttackGraph:
    from pathfinder.dashboard.attack_path import AttackGraph

    graph = AttackGraph()
    for node in security_graph["nodes"]:
        graph.add_node(
            node["id"],
            entry=bool(node.get("entrypoint_flag")),
            end=bool(node.get("target_flag")),
            **_node_metrics(node),
        )
    for edge in security_graph["attack_edges"]:
        graph.add_edge(edge["source"], edge["target"], **_edge_metrics(edge))
    graph.build_graph()
    graph.best_path = list(selected_path["nodes"])
    graph.best_score = float(selected_path["score"])
    return graph


def _build_service_dashboard(*, security_graph: dict[str, object], selected_path: dict[str, object]) -> ServiceAttackGraph:
    from pathfinder.dashboard.service_graph import ServiceAttackGraph

    graph = ServiceAttackGraph()
    for node in security_graph["nodes"]:
        graph.add_node(
            node["id"],
            node.get("label", node["id"]),
            "inferred",
            "service",
            node.get("rationale", ""),
            list(node.get("focal_file_paths", [])),
            len(node.get("focal_file_paths", [])),
            {node.get("language", "unknown"): len(node.get("focal_file_paths", [])) or 1},
            node.get("rationale", ""),
            entry=bool(node.get("entrypoint_flag")),
            end=bool(node.get("target_flag")),
            **_node_metrics(node),
        )
        dashboard_node = graph.nodes[node["id"]]
        dashboard_node.summary = node.get("rationale", dashboard_node.summary)
        dashboard_node.files = list(node.get("focal_file_paths", []))
        dashboard_node.file_count = len(dashboard_node.files)
        dashboard_node.files_by_language = {node.get("language", "unknown"): len(dashboard_node.files) or 1}
    for edge in security_graph["attack_edges"]:
        graph.add_edge(edge["source"], edge["target"], **_edge_metrics(edge))
    graph.build_graph()
    graph.best_path = list(selected_path["nodes"])
    graph.best_score = float(selected_path["score"])
    return graph


def _node_metrics(node_payload: dict[str, object]) -> dict[str, float]:
    security_scores = node_payload.get("security_scores", {})
    return {
        "exploitability": float(security_scores.get("exploitability", 0.0)),
        "privelidge_gain": float(security_scores.get("privilege_gain", 0.0)),
        "data_access_value": float(security_scores.get("data_access_value", 0.0)),
        "lateral_movement_value": float(security_scores.get("lateral_movement_value", 0.0)),
        "detection_risk": float(security_scores.get("detection_risk", 0.0)),
        "normalised_risk_score": float(node_payload.get("normalized_risk_score", 0.0)),
        "confidence": float(node_payload.get("confidence", 0.0)),
    }


def _edge_metrics(edge_payload: dict[str, object]) -> dict[str, object]:
    return {
        "vulnerability": edge_payload.get("attack_type", "default"),
        "transition_likelihood": float(edge_payload.get("transition_likelihood", 0.0)),
        "detection_risk": float(edge_payload.get("detection_risk", 0.0)),
        "edge_attack_cost": float(edge_payload.get("edge_attack_cost", 0.0)),
    }


def _recommendation_report_html(recommendation_report) -> str:
    cards = []
    for item in recommendation_report.recommendations:
        steps = "".join(f"<li>{step}</li>" for step in item.mitigation_steps)
        cards.append(
            f"""
            <div class="card" style="padding:16px; margin-bottom:12px;">
              <h3 style="margin:0 0 8px;">{item.title}</h3>
              <p style="margin:0 0 10px;"><b>Priority:</b> {item.priority}</p>
              <p style="margin:0 0 10px;">{item.summary}</p>
              <p style="margin:0 0 10px;"><b>Primary file:</b> <code>{item.primary_file_path}</code></p>
              <ul>{steps}</ul>
            </div>
            """
        )
    return "".join(cards) or "<p>No recommendations generated.</p>"


def _build_dashboard_fallback_html(*, selected_path: dict[str, object], report_html: str) -> str:
    steps = "".join(f"<li><b>Step {index + 1}</b>: {edge['source']} -> {edge['target']} via {edge['attack_type']}</li>" for index, edge in enumerate(selected_path.get("edge_details", [])))
    return f"""
<html>
<head>
<title>Pathfinder Attack Path Dashboard</title>
</head>
<body>
<h1>Pathfinder Attack Path Dashboard</h1>
<h2>Attack Path</h2>
<ol>{steps}</ol>
<h2>Recommendation Report</h2>
{report_html}
</body>
</html>
"""


def _node_role(node: dict[str, object]) -> str | None:
    if node.get("entrypoint_flag"):
        return "entry"
    if node.get("target_flag"):
        return "target"
    return "transition"


def _infer_language(path: str) -> str:
    if path.endswith(".py"):
        return "python"
    if path.endswith(".ts"):
        return "typescript"
    if path.endswith(".js"):
        return "javascript"
    return "unknown"


@dataclass(frozen=True, slots=True)
class SecurityNodeWorkItem:
    node_id: str
    node_payload: dict[str, object]
    analysis_file_path: str
    analysis_code: str | None = None
    absolute_path: str | None = None


@dataclass(frozen=True, slots=True)
class SecurityEdgeWorkItem:
    edge_id: str
    edge_payload: dict[str, object]
    source_node_id: str
    target_node_id: str
    source_file_path: str
    target_file_path: str
    source_node_payload: dict[str, object] | None = None
    target_node_payload: dict[str, object] | None = None
    source_code: str | None = None
    target_code: str | None = None


@dataclass(frozen=True, slots=True)
class SecurityGraphInput:
    graph_id: str
    graph_mode: str
    repo_path: str
    nodes: list[SecurityNodeWorkItem]
    edges: list[SecurityEdgeWorkItem]
    edge_depends_on_nodes: bool = True


class _SecurityNodeStage:
    kind = StageKind.ENRICH

    def __init__(self, *, work_item: SecurityNodeWorkItem, ai: PathfinderAI) -> None:
        self._work_item = work_item
        self._ai = ai

    async def execute(self, ctx: StageContext) -> dict[str, object]:
        if self._work_item.analysis_code is not None and hasattr(self._ai, "analyze_node_content"):
            analyzed = await asyncio.to_thread(
                self._ai.analyze_node_content,
                self._work_item.analysis_file_path,
                self._work_item.analysis_code,
            )
        else:
            target = self._work_item.absolute_path or self._work_item.analysis_file_path
            analyzed = await asyncio.to_thread(self._ai.analyze_node, target)
        analyzed.update(self._work_item.node_payload)
        return analyzed


class _SecurityEdgeStage:
    kind = StageKind.ENRICH

    def __init__(self, *, work_item: SecurityEdgeWorkItem, ai: PathfinderAI, node_stage_names: dict[str, str]) -> None:
        self._work_item = work_item
        self._ai = ai
        self._node_stage_names = node_stage_names

    async def execute(self, ctx: StageContext) -> dict[str, object]:
        source_node = (
            _stage_data(ctx, self._node_stage_names[self._work_item.source_node_id])
            if self._work_item.source_node_payload is None
            else dict(self._work_item.source_node_payload)
        )
        target_node = (
            _stage_data(ctx, self._node_stage_names[self._work_item.target_node_id])
            if self._work_item.target_node_payload is None
            else dict(self._work_item.target_node_payload)
        )
        if self._work_item.source_code is not None and self._work_item.target_code is not None and hasattr(self._ai, "analyze_edge_content"):
            analyzed = await asyncio.to_thread(
                self._ai.analyze_edge_content,
                structural_edge=self._work_item.edge_payload,
                source_id=self._work_item.source_node_id,
                target_id=self._work_item.target_node_id,
                source_path=self._work_item.source_file_path,
                target_path=self._work_item.target_file_path,
                source_code=self._work_item.source_code,
                target_code=self._work_item.target_code,
            )
        else:
            analyzed = await asyncio.to_thread(
                self._ai.analyze_edge,
                self._work_item.edge_payload,
                source_node,
                target_node,
            )
        if not analyzed:
            return {}
        edge_result = dict(analyzed[0])
        edge_result.setdefault("edge_payload", dict(self._work_item.edge_payload))
        return edge_result


class _SecurityAggregateStage:
    kind = StageKind.TRANSFORM

    def __init__(
        self,
        *,
        graph_id: str,
        graph_mode: str,
        repo_path: str,
        node_stage_names: dict[str, str],
        edge_stage_names: dict[str, str],
    ) -> None:
        self._graph_id = graph_id
        self._graph_mode = graph_mode
        self._repo_path = repo_path
        self._node_stage_names = node_stage_names
        self._edge_stage_names = edge_stage_names

    async def execute(self, ctx: StageContext) -> dict[str, object]:
        nodes = [dict(_stage_data(ctx, stage_name)) for _, stage_name in sorted(self._node_stage_names.items())]
        attack_edges = []
        for _, stage_name in sorted(self._edge_stage_names.items()):
            item = _stage_data(ctx, stage_name)
            if item:
                attack_edges.append(dict(item))
        return {
            "graph_id": self._graph_id,
            "version": "mvp-v1",
            "repo_path": self._repo_path,
            "graph_mode": self._graph_mode,
            "nodes": nodes,
            "structural_edges": [edge["edge_payload"] for edge in attack_edges],
            "attack_edges": attack_edges,
        }


async def _run_security_subpipeline(*, graph_input: SecurityGraphInput, ai: PathfinderAI, timeout_seconds: float, provider: str) -> dict[str, object]:
    TimeoutInterceptor.DEFAULT_TIMEOUT_MS = max(int(timeout_seconds * 1000), 1)
    node_stage_names = {item.node_id: f"node::{item.node_id}" for item in graph_input.nodes}
    edge_stage_names = {item.edge_id: f"edge::{item.edge_id}" for item in graph_input.edges}
    pipeline = Pipeline(name=f"security_{graph_input.graph_mode}")
    previous_node_stage_name: str | None = None
    serialize = provider == "minimax"
    for item in graph_input.nodes:
        dependencies: tuple[str, ...] = ()
        if serialize and previous_node_stage_name is not None:
            dependencies = (previous_node_stage_name,)
        pipeline = pipeline.with_stage(
            node_stage_names[item.node_id],
            _SecurityNodeStage(work_item=item, ai=ai),
            StageKind.ENRICH,
            dependencies=dependencies,
        )
        previous_node_stage_name = node_stage_names[item.node_id]
    previous_edge_stage_name: str | None = None
    for item in graph_input.edges:
        edge_dependencies = (
            (node_stage_names[item.source_node_id], node_stage_names[item.target_node_id])
            if graph_input.edge_depends_on_nodes
            else ()
        )
        if serialize and previous_edge_stage_name is not None:
            edge_dependencies = edge_dependencies + (previous_edge_stage_name,)
        pipeline = pipeline.with_stage(
            edge_stage_names[item.edge_id],
            _SecurityEdgeStage(work_item=item, ai=ai, node_stage_names=node_stage_names),
            StageKind.ENRICH,
            dependencies=edge_dependencies,
        )
        previous_edge_stage_name = edge_stage_names[item.edge_id]
    pipeline = pipeline.with_stage(
        "aggregate_security_graph",
        _SecurityAggregateStage(
            graph_id=graph_input.graph_id,
            graph_mode=graph_input.graph_mode,
            repo_path=graph_input.repo_path,
            node_stage_names=node_stage_names,
            edge_stage_names=edge_stage_names,
        ),
        StageKind.TRANSFORM,
        dependencies=tuple(sorted(node_stage_names.values()) + sorted(edge_stage_names.values())),
    )
    results = await pipeline.run(
        interceptors=[LoggingInterceptor(), MetricsInterceptor()],
        emit_stage_wide_events=False,
        emit_pipeline_wide_event=False,
        topology=f"security_subpipeline_{graph_input.graph_mode}",
        execution_mode="default",
    )
    failed_stages = results.failed()
    if failed_stages:
        raise ValidationError("Security subpipeline failed", context={"failed_stages": failed_stages, "graph_mode": graph_input.graph_mode})
    return results.data("aggregate_security_graph")


def _build_service_security_graph_input(*, repo_path: Path, service_graph_path: Path) -> SecurityGraphInput:
    service_graph = read_service_graph(service_graph_path)
    nodes: list[SecurityNodeWorkItem] = []
    for service_node in service_graph.nodes:
        summary_text = _service_node_prompt_text(repo_path=repo_path, service_node=service_node)
        representative_path = service_node.member_file_paths[0] if service_node.member_file_paths else service_node.id
        node_payload = _service_node_payload(service_node=service_node, representative_path=representative_path)
        nodes.append(
            SecurityNodeWorkItem(
                node_id=service_node.id,
                analysis_file_path=f"service://{service_node.id}",
                analysis_code=summary_text,
                absolute_path=str(repo_path / representative_path) if service_node.member_file_paths else None,
                node_payload=node_payload,
            )
        )

    edges: list[SecurityEdgeWorkItem] = []
    service_node_by_id = {item.id: item for item in service_graph.nodes}
    for service_edge in service_graph.service_edges:
        source_node = service_node_by_id[service_edge.source]
        target_node = service_node_by_id[service_edge.target]
        source_representative_path = source_node.member_file_paths[0] if source_node.member_file_paths else source_node.id
        target_representative_path = target_node.member_file_paths[0] if target_node.member_file_paths else target_node.id
        source_node_payload = _service_node_payload(service_node=source_node, representative_path=source_representative_path)
        target_node_payload = _service_node_payload(service_node=target_node, representative_path=target_representative_path)
        edge_payload = {
            "id": service_edge.id,
            "relationship_type": ",".join(service_edge.relationship_types) if service_edge.relationship_types else "service_relation",
            "source": service_edge.source,
            "target": service_edge.target,
            "supporting_structural_edge_ids": list(service_edge.supporting_structural_edge_ids),
        }
        edges.append(
            SecurityEdgeWorkItem(
                edge_id=service_edge.id,
                edge_payload=edge_payload,
                source_node_id=service_edge.source,
                target_node_id=service_edge.target,
                source_file_path=f"service://{source_node.id}",
                target_file_path=f"service://{target_node.id}",
                source_node_payload=source_node_payload,
                target_node_payload=target_node_payload,
                source_code=_service_edge_node_prompt_text(repo_path=repo_path, service_node=source_node),
                target_code=_service_edge_node_prompt_text(repo_path=repo_path, service_node=target_node),
            )
        )
    return SecurityGraphInput(
        graph_id=service_graph.service_graph_id,
        graph_mode="service",
        repo_path=service_graph.repo_path,
        nodes=nodes,
        edges=edges,
        edge_depends_on_nodes=False,
    )


def _build_file_security_graph_input(*, artifact, repo_path: Path) -> SecurityGraphInput:
    nodes = [
        SecurityNodeWorkItem(
            node_id=node.path,
            analysis_file_path=str(repo_path / node.path),
            absolute_path=str(repo_path / node.path),
            node_payload={"id": node.path, "path": node.path, "language": node.language, "entrypoint_flag": node.entrypoint_flag, "target_flag": node.target_flag},
        )
        for node in artifact.nodes
    ]
    edges = [
        SecurityEdgeWorkItem(
            edge_id=edge.id,
            edge_payload={
                "id": edge.id,
                "relationship_type": edge.relationship_type.value,
                "source": edge.source,
                "target": edge.target,
                "supporting_structural_edge_ids": [edge.id],
            },
            source_node_id=edge.source,
            target_node_id=edge.target,
            source_file_path=str(repo_path / edge.source),
            target_file_path=str(repo_path / edge.target),
            absolute_path=None,
        )
        for edge in artifact.structural_edges
    ]
    return SecurityGraphInput(
        graph_id=artifact.graph_id,
        graph_mode="file",
        repo_path=artifact.repo_path,
        nodes=nodes,
        edges=edges,
        edge_depends_on_nodes=True,
    )


def _service_node_prompt_text(*, repo_path: Path, service_node) -> str:
    member_summaries = []
    for path in service_node.member_file_paths[:8]:
        absolute_path = repo_path / path
        preview = absolute_path.read_text(encoding="utf-8", errors="replace")[:1200] if absolute_path.exists() else ""
        member_summaries.append({"path": path, "preview": preview})
    return json.dumps(
        {
            "service_id": service_node.id,
            "service_name": service_node.name,
            "layer": service_node.layer.value,
            "summary": service_node.summary,
            "file_count": service_node.file_count,
            "files_by_language": service_node.files_by_language,
            "member_file_paths": service_node.member_file_paths,
            "member_file_previews": member_summaries,
        },
        indent=2,
        sort_keys=True,
    )


def _service_edge_node_prompt_text(*, repo_path: Path, service_node) -> str:
    return _service_node_prompt_text(repo_path=repo_path, service_node=service_node)


def _service_node_payload(*, service_node, representative_path: str) -> dict[str, object]:
    return {
        "id": service_node.id,
        "path": representative_path,
        "label": service_node.name,
        "language": _dominant_language(service_node.files_by_language),
        "entrypoint_flag": service_node.layer.value in {"edge", "presentation", "interface"} or any(_looks_like_entry(path) for path in service_node.member_file_paths),
        "target_flag": service_node.layer.value in {"data", "shared"} or any(_looks_like_target(path) for path in service_node.member_file_paths),
        "focal_file_paths": list(service_node.member_file_paths),
    }


def _dominant_language(files_by_language: dict[str, int]) -> str:
    if not files_by_language:
        return "unknown"
    return sorted(files_by_language.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _looks_like_entry(path: str) -> bool:
    return any(token in path for token in ("api", "web", "public", "cli", "dashboard", "routes", "server", "main"))


def _looks_like_target(path: str) -> bool:
    return any(token in path for token in ("db", "admin", "vault", "config"))
