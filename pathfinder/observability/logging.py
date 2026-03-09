"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping


def configure_logging(*, verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    fields: Mapping[str, object] | None = None,
) -> None:
    payload: dict[str, object] = {"event": event}
    if fields:
        payload.update(fields)
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))
