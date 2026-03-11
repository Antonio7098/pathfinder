"""Stable identifier helpers for service overlay artifacts."""

from __future__ import annotations

import re


SHARED_UTILITY_SERVICE_ID = "svc:shared-utility"
UNCLASSIFIED_SERVICE_ID = "svc:unclassified"


def slugify_service_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "service"


def service_id_from_name(name: str) -> str:
    return f"svc:{slugify_service_name(name)}"


def service_grouping_id_for_graph(graph_id: str) -> str:
    return f"sg:{graph_id}"


def service_graph_id_for_graph(graph_id: str) -> str:
    return f"svg:{graph_id}"


def service_edge_id(source: str, target: str) -> str:
    return f"sve:{source}->{target}"