"""Langfuse observability for Sentinel V2.

Connects to the shared Langfuse instance in synapseia-network.
Configure via .env:
  LANGFUSE_PUBLIC_KEY   — project public key (default: pk-lf-synapseia-dev)
  LANGFUSE_SECRET_KEY   — project secret key (default: sk-lf-synapseia-dev)
  LANGFUSE_HOST         — Langfuse URL (default: http://host.docker.internal:3700)
  LANGFUSE_ENABLED      — set to "false" to disable (default: true)

All functions are no-ops when disabled or when the client fails to init,
so tracing never breaks the pipeline.
"""
from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Optional

log = logging.getLogger("sentinel_v2.tracing")

_client: Any = None
_enabled: bool = False


def _init() -> None:
    global _client, _enabled
    if os.getenv("LANGFUSE_ENABLED", "true").lower() in ("false", "0", "no"):
        log.info("Langfuse tracing disabled via LANGFUSE_ENABLED=false")
        return
    try:
        from langfuse import Langfuse  # type: ignore[import-untyped]

        host = os.getenv("LANGFUSE_HOST", "http://host.docker.internal:3700")
        _client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-synapseia-dev"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-synapseia-dev"),
            host=host,
        )
        _enabled = True
        log.info("Langfuse tracing -> %s", host)
    except Exception as exc:  # noqa: BLE001
        log.warning("Langfuse init failed (tracing disabled): %s", exc)


_init()


def get_langfuse() -> Any:
    return _client


def start_trace(
    name: str,
    *,
    cycle: Optional[int] = None,
    draft_id: Optional[str] = None,
    opportunity: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Any:
    """Create and return a Langfuse trace for a pipeline phase.

    Returns None if tracing is disabled. Callers pass this to
    ``log_event`` and ``end_trace`` - both accept None safely.
    """
    if not _enabled or _client is None:
        return None
    tags: list[str] = []
    if cycle is not None:
        tags.append(f"cycle:{cycle}")
    if draft_id:
        tags.append(f"draft:{draft_id}")
    meta: dict = {}
    if cycle is not None:
        meta["cycle"] = cycle
    if draft_id:
        meta["draft_id"] = draft_id
    if opportunity:
        meta["opportunity"] = opportunity
    if metadata:
        meta.update(metadata)
    try:
        return _client.trace(
            name=f"sentinel.{name}",
            tags=tags or None,
            metadata=meta or None,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("start_trace failed: %s", exc)
        return None


def log_event(
    trace: Any,
    event_name: str,
    *,
    level: str = "DEFAULT",
    metadata: Optional[dict] = None,
) -> None:
    """Attach a named event to a trace. No-op if trace is None."""
    if trace is None or not _enabled:
        return
    with contextlib.suppress(Exception):
        trace.event(name=event_name, level=level, metadata=metadata or {})


def end_trace(trace: Any, *, output: Optional[dict] = None, level: str = "DEFAULT") -> None:
    """Finalise a trace and flush. No-op if trace is None."""
    if trace is None or not _enabled or _client is None:
        return
    with contextlib.suppress(Exception):
        if output is not None:
            trace.update(output=output, level=level)
        _client.flush()
