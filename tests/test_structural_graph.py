from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pathfinder.structural.io import read_structural_graph
from pathfinder.structural.service import StructuralExtractionRequest, StructuralExtractionService


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def build_artifact(repo_name: str, tmp_path: Path):
    from pathfinder.observability.logging import get_logger

    service = StructuralExtractionService(get_logger("test"))
    output_path = tmp_path / f"{repo_name}_structural_graph.json"
    result = service.run(
        StructuralExtractionRequest(
            repo_path=FIXTURES / repo_name,
            output_path=output_path,
            raw_codegraph_output_path=tmp_path / f"{repo_name}_raw_codegraph.json",
        )
    )
    return result, read_structural_graph(output_path)


def test_extracts_python_structural_graph(tmp_path: Path) -> None:
    result, artifact = build_artifact("python_repo", tmp_path)

    assert result.output_path.exists()
    assert artifact.summary.file_count == 3
    assert [node.path for node in artifact.nodes] == ["pkg/db.py", "pkg/service.py", "web/routes.py"]

    edge_ids = [edge.id for edge in artifact.structural_edges]
    assert edge_ids == [
        "se:pkg/service.py->pkg/db.py:calls",
        "se:pkg/service.py->pkg/db.py:imports",
        "se:web/routes.py->pkg/service.py:calls",
        "se:web/routes.py->pkg/service.py:imports",
    ]

    imports_edge = next(edge for edge in artifact.structural_edges if edge.id == "se:web/routes.py->pkg/service.py:imports")
    assert imports_edge.evidence_count == 2
    assert imports_edge.evidence_relations == ["imports", "imports_symbol"]
    assert any(item.target_symbol == "get_user" for item in imports_edge.provenance)

    calls_edge = next(edge for edge in artifact.structural_edges if edge.id == "se:web/routes.py->pkg/service.py:calls")
    assert calls_edge.evidence_count == 1
    assert calls_edge.evidence_relations == ["uses_symbol"]
    assert calls_edge.provenance[0].source_symbol == "handler"
    assert calls_edge.provenance[0].target_symbol == "get_user"

    assert artifact.summary.edges_by_relationship_type == {"calls": 2, "imports": 2}
    assert artifact.summary.files_by_language == {"python": 3}


def test_excludes_self_edges_and_tracks_diagnostics(tmp_path: Path) -> None:
    _, artifact = build_artifact("python_local_only", tmp_path)

    assert artifact.summary.file_count == 1
    assert artifact.summary.structural_edge_count == 0
    assert artifact.diagnostics.dropped_self_edges >= 1


def test_extracts_typescript_structural_graph(tmp_path: Path) -> None:
    _, artifact = build_artifact("ts_repo", tmp_path)

    assert [node.path for node in artifact.nodes] == ["src/api.ts", "src/db.ts", "src/service.ts"]
    assert artifact.summary.files_by_language == {"typescript": 3}
    assert artifact.summary.structural_edge_count == 4
    assert {edge.relationship_type.value for edge in artifact.structural_edges} == {"imports", "calls"}


def test_maps_python_reexports_to_structural_imports(tmp_path: Path) -> None:
    _, artifact = build_artifact("python_reexports", tmp_path)

    assert [node.path for node in artifact.nodes] == ["pkg/__init__.py", "pkg/service.py"]
    edge_ids = [edge.id for edge in artifact.structural_edges]
    assert edge_ids == ["se:pkg/__init__.py->pkg/service.py:imports"]
    edge = artifact.structural_edges[0]
    assert "reexports" in edge.evidence_relations
    assert any(item.raw_relation == "reexports" for item in edge.provenance)
    assert any(item.target_symbol == "get_user" for item in edge.provenance)


def test_maps_typescript_reexports_to_structural_imports(tmp_path: Path) -> None:
    _, artifact = build_artifact("ts_reexports", tmp_path)

    assert [node.path for node in artifact.nodes] == ["src/index.ts", "src/service.ts"]
    edge_ids = [edge.id for edge in artifact.structural_edges]
    assert edge_ids == ["se:src/index.ts->src/service.ts:imports"]
    edge = artifact.structural_edges[0]
    assert "reexports" in edge.evidence_relations
    assert any(item.raw_relation == "reexports" for item in edge.provenance)


def test_json_output_is_deterministic(tmp_path: Path) -> None:
    result_one, artifact_one = build_artifact("python_repo", tmp_path / "run_one")
    result_two, artifact_two = build_artifact("python_repo", tmp_path / "run_two")

    assert artifact_one.model_dump(mode="json") == artifact_two.model_dump(mode="json")
    assert result_one.output_path.read_text(encoding="utf-8") == result_two.output_path.read_text(encoding="utf-8")


def test_excludes_generated_and_environment_directories_by_default(tmp_path: Path) -> None:
    _, artifact = build_artifact("python_with_generated", tmp_path)

    assert [node.path for node in artifact.nodes] == ["src/app.py"]
    assert artifact.summary.file_count == 1
    assert artifact.summary.structural_edge_count == 0


def test_cli_end_to_end(tmp_path: Path) -> None:
    output_path = tmp_path / "cli_structural_graph.json"
    raw_output_path = tmp_path / "cli_raw_codegraph.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pathfinder.cli",
            "build-structural-graph",
            "--repo",
            str(FIXTURES / "python_repo"),
            "--output",
            str(output_path),
            "--raw-codegraph-output",
            str(raw_output_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert output_path.exists()
    assert raw_output_path.exists()
    summary = json.loads(completed.stdout.strip())
    assert summary["file_count"] == 3
    assert summary["structural_edge_count"] == 4
