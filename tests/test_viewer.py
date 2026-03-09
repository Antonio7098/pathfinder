from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from pathfinder.observability.logging import get_logger
from pathfinder.structural.service import StructuralExtractionRequest, StructuralExtractionService
from pathfinder.viewer.server import GraphViewerConfig, create_viewer_server


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def build_graph_artifact(tmp_path: Path) -> Path:
    service = StructuralExtractionService(get_logger("viewer-test"))
    output_path = tmp_path / "structural_graph.json"
    service.run(
        StructuralExtractionRequest(
            repo_path=FIXTURES / "python_repo",
            output_path=output_path,
        )
    )
    return output_path


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url) as response:  # noqa: S310
        return response.read().decode("utf-8")


def test_viewer_serves_index_and_graph_json(tmp_path: Path) -> None:
    graph_path = build_graph_artifact(tmp_path)
    server = create_viewer_server(GraphViewerConfig(port=0, graph_path=graph_path), get_logger("viewer-test"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        index_html = fetch_text(f"http://{host}:{port}/")
        graph_json = fetch_text(f"http://{host}:{port}/api/graph")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert "Pathfinder Viewer" in index_html
    payload = json.loads(graph_json)
    assert payload["summary"]["file_count"] == 3
    assert payload["summary"]["structural_edge_count"] == 4


def test_viewer_returns_404_when_no_graph_configured() -> None:
    server = create_viewer_server(GraphViewerConfig(port=0), get_logger("viewer-test"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        with urllib.request.urlopen(f"http://{host}:{port}/api/graph") as response:  # pragma: no cover
            response.read()
    except urllib.error.HTTPError as error:
        assert error.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
