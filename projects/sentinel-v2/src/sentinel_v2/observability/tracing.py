"""Langfuse v4 observability for Sentinel V2.

Connects to the shared Langfuse v3+ instance in synapseia-network.
Configure via .env:
  LANGFUSE_PUBLIC_KEY   — project public key (default: pk-lf-synapseia-dev)
  LANGFUSE_SECRET_KEY   — project secret key (default: sk-lf-synapseia-dev)
  LANGFUSE_HOST         — Langfuse URL (default: http://host.docker.internal:3700)
  LANGFUSE_ENABLED      — set to "false" to disable (default: true)

All functions are no-ops when disabled or when the client fails to init,
so tracing never breaks the pipeline.

The langfuse v4 SDK is OpenTelemetry-based. We use the imperative API:
  client.start_observation(name=..., as_type='chain') -> LangfuseSpan
  span.create_event(name=..., level=..., metadata=...)
  span.update(output=..., level=...)
  span.end()
"""
from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Optional

log = logging.getLogger("sentinel_v2.tracing")

# Cap OTel exporter timeout BEFORE the Langfuse import (which loads the OTel
# SDK transitively). The v4 SDK reads these env vars on first instantiation.
# Default of 10s lets a missing Langfuse hold each `flush()` open long enough
# to stall the cycle. 2s keeps tracing best-effort without blocking phases.
os.environ.setdefault("OTEL_EXPORTER_OTLP_TIMEOUT", "2000")
os.environ.setdefault("OTEL_EXPORTER_OTLP_TRACES_TIMEOUT", "2000")

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
    """Create and return a Langfuse span (root observation) for a phase.

    Returns None if tracing is disabled. Callers pass this to
    ``log_event`` and ``end_trace`` - both accept None safely.
    """
    if not _enabled or _client is None:
        return None
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
        return _client.start_observation(
            name=f"sentinel.{name}",
            as_type="chain",
            metadata=meta or None,
            input={"cycle": cycle, "draft_id": draft_id, "opportunity": opportunity},
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("start_trace failed: %s", exc)
        return None


def log_event(
    span: Any,
    event_name: str,
    *,
    level: str = "DEFAULT",
    metadata: Optional[dict] = None,
) -> None:
    """Attach a named event to a span. No-op if span is None."""
    if span is None or not _enabled:
        return
    with contextlib.suppress(Exception):
        span.create_event(name=event_name, level=level, metadata=metadata or {})


def end_trace(span: Any, *, output: Optional[dict] = None, level: str = "DEFAULT") -> None:
    """Update span with output, end it, and flush. No-op if span is None."""
    if span is None or not _enabled or _client is None:
        return
    with contextlib.suppress(Exception):
        if output is not None:
            span.update(output=output, level=level)
        span.end()
        _client.flush()
