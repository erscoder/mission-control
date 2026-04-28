"""LLM configuration helpers — use MiniMax from environment."""
from __future__ import annotations

import logging
import os
import re
import time

from crewai import LLM

log = logging.getLogger("sentinel_v2.llm")

# Cached LLM instances per model name
_llm_cache: dict[str, LLM] = {}

# Global litellm patch flag
_litellm_patched: bool = False


def _patch_litellm_system_messages() -> None:
    """Monkey-patch litellm.completion and litellm.acompletion to convert
    ``system`` role messages to ``user`` before they hit the API.

    MiniMax rejects ``system`` role (error 2013). The per-LLM patch in
    ``_patch_system_messages`` covers most paths, but CrewAI hierarchical
    process and litellm internals can bypass it. This global patch is a
    safety net that catches ALL calls.

    Idempotent — guarded by ``_litellm_patched`` module flag.
    """
    global _litellm_patched
    if _litellm_patched:
        return
    _litellm_patched = True

    try:
        import litellm
    except ImportError:
        return

    def _rewrite_system(messages):
        if not messages:
            return messages
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                msg["role"] = "user"
        return messages

    _original_completion = litellm.completion

    def _patched_completion(*args, **kwargs):
        if "messages" in kwargs:
            kwargs["messages"] = _rewrite_system(kwargs["messages"])
        elif args:
            args = list(args)
            # litellm.completion(model, messages, ...)
            if len(args) >= 2 and isinstance(args[1], list):
                args[1] = _rewrite_system(args[1])
            args = tuple(args)
        return _original_completion(*args, **kwargs)

    litellm.completion = _patched_completion

    _original_acompletion = litellm.acompletion

    async def _patched_acompletion(*args, **kwargs):
        if "messages" in kwargs:
            kwargs["messages"] = _rewrite_system(kwargs["messages"])
        elif args:
            args = list(args)
            if len(args) >= 2 and isinstance(args[1], list):
                args[1] = _rewrite_system(args[1])
            args = tuple(args)
        return await _original_acompletion(*args, **kwargs)

    litellm.acompletion = _patched_acompletion


def get_minimax_llm(model: str = "MiniMax-M2.7") -> LLM:
    """
    Return a CrewAI LLM configured for MiniMax.

    Reads from environment:
    - MINIMAX_API_KEY (required)
    - MINIMAX_BASE_URL (default: https://api.minimax.io/v1)

    Usage:
        llm = get_minimax_llm()
        llm = get_minimax_llm("MiniMax-M2.7")
    """
    if model in _llm_cache:
        return _llm_cache[model]

    _patch_litellm_system_messages()

    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MINIMAX_API_KEY not set. Add it to .env or export it before running."
        )

    base_url = os.environ.get(
        "MINIMAX_BASE_URL", "https://api.minimax.io/v1"
    )

    llm = LLM(
        model=model,
        base_url=base_url,
        api_key=api_key,
    )
    _patch_system_messages(llm)
    _patch_empty_response_retry(llm)
    _llm_cache[model] = llm
    return llm


def _patch_empty_response_retry(
    llm: LLM,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> LLM:
    """Retry the LLM ``call`` when MiniMax returns ``None``/empty/whitespace.

    Background: MiniMax (especially M2.7) periodically streams back an empty
    body, surfacing as ``Invalid response from LLM call - None or empty.``
    inside CrewAI. CrewAI then constructs a ``TaskOutput`` from ``None``,
    which Pydantic rejects with ``string_type`` validation, crashing the
    crew. Retrying with backoff is enough to recover most cases.

    Idempotent — safe to call multiple times on the same instance.
    """
    if getattr(llm, "_empty_retry_patched", False):
        return llm

    original_call = llm.call

    def _retrying_call(*args, **kwargs):
        last: object | None = None
        for attempt in range(1, max_retries + 1):
            result = original_call(*args, **kwargs)
            last = result
            if result is None:
                payload = ""
            elif isinstance(result, str):
                payload = result
            else:
                payload = str(result)
            if payload.strip():
                return result
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                log.warning(
                    "MiniMax empty response, retry %d/%d in %.1fs",
                    attempt, max_retries, delay,
                )
                time.sleep(delay)
        raise RuntimeError(
            f"MiniMax returned empty after {max_retries} retries (last={last!r})"
        )

    llm.call = _retrying_call  # type: ignore[method-assign]
    llm._empty_retry_patched = True  # type: ignore[attr-defined]
    return llm


def _patch_system_messages(llm: LLM) -> LLM:
    """Rewrite ``system`` role messages to ``user`` before calling the API.

    MiniMax rejects ``system`` role (error 2013). CrewAI sends agent
    backstory/role as system messages. This mirrors the O1 conversion
    already in crewai/llm.py lines 1711-1716.

    Idempotent — safe to call multiple times on the same instance.
    """
    if getattr(llm, "_system_patched", False):
        return llm

    original_call = llm.call

    def _patched_call(messages, *args, **kwargs):
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                msg["role"] = "user"
        return original_call(messages, *args, **kwargs)

    llm.call = _patched_call  # type: ignore[method-assign]
    llm._system_patched = True  # type: ignore[attr-defined]
    return llm


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def make_clean_llm(llm: LLM) -> LLM:
    """Wrap an LLM so its call() strips <think>...</think> from string responses.

    Idempotent — safe to call multiple times on the same instance.
    Needed for MiniMax reasoning models used in memory layers that expect clean JSON.
    """
    if getattr(llm, "_think_stripped", False):
        return llm

    original_call = llm.call

    def _clean_call(*args, **kwargs):
        result = original_call(*args, **kwargs)
        if isinstance(result, str):
            result = _THINK_RE.sub("", result).strip()
        return result

    llm.call = _clean_call  # type: ignore[method-assign]
    llm._think_stripped = True  # type: ignore[attr-defined]
    return llm


def get_ollama_embedder_config() -> dict:
    """Return Ollama embedder config dict for CrewAI memory."""
    from sentinel_v2.config.embedder_config import get_ollama_embedder_config as _get
    return _get()