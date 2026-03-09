"""Minimal HTTP server for the Pathfinder graph viewer."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from pathfinder.errors import ConfigurationError, PersistenceError
from pathfinder.observability.logging import log_event
from pathfinder.structural.io import read_structural_graph


class GraphViewerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: str = "127.0.0.1"
    port: int = 8000
    graph_path: Path | None = None


def create_viewer_server(config: GraphViewerConfig, logger) -> ThreadingHTTPServer:
    graph_payload = _load_graph_payload(config.graph_path) if config.graph_path else None

    class GraphViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path in {"/", "/index.html"}:
                self._serve_asset("index.html")
                return
            if self.path == "/styles.css":
                self._serve_asset("styles.css")
                return
            if self.path == "/app.js":
                self._serve_asset("app.js")
                return
            if self.path == "/api/graph":
                if graph_payload is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "No graph artifact configured")
                    return
                self._send_json(graph_payload)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            log_event(
                logger,
                "viewer.http.request",
                fields={
                    "path": self.path,
                    "client_address": self.client_address[0],
                    "message": format % args,
                },
            )

        def _serve_asset(self, name: str) -> None:
            asset_path = files("pathfinder.viewer.assets").joinpath(name)
            if not asset_path.is_file():
                raise ConfigurationError("Viewer asset is missing", context={"asset_name": name})
            payload = asset_path.read_bytes()
            content_type, _ = mimetypes.guess_type(name)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, payload: dict[str, object]) -> None:
            raw = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer((config.host, config.port), GraphViewerHandler)
    log_event(
        logger,
        "viewer.server.created",
        fields={
            "host": config.host,
            "port": cast(tuple[str, int], server.server_address)[1],
            "graph_path": str(config.graph_path) if config.graph_path else None,
        },
    )
    return server


def serve_graph_viewer(config: GraphViewerConfig, logger) -> int:
    server = create_viewer_server(config, logger)
    host, port = cast(tuple[str, int], server.server_address)
    log_event(
        logger,
        "viewer.server.started",
        fields={"host": host, "port": port, "graph_path": str(config.graph_path) if config.graph_path else None},
    )
    print(f"Viewer available at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log_event(logger, "viewer.server.stopped", fields={"host": host, "port": port})
    finally:
        server.server_close()
    return 0


def _load_graph_payload(graph_path: Path) -> dict[str, object]:
    resolved_path = graph_path.resolve()
    if not resolved_path.exists() or not resolved_path.is_file():
        raise ConfigurationError("Graph artifact path does not exist or is not a file", context={"graph_path": str(resolved_path)})
    try:
        artifact = read_structural_graph(resolved_path)
    except PersistenceError:
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise PersistenceError("Failed to load viewer graph artifact", context={"graph_path": str(resolved_path), "cause": str(exc)}) from exc
    return cast(dict[str, object], artifact.model_dump(mode="json"))
