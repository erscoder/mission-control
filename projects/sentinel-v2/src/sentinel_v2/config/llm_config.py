"""LLM configuration helpers — use MiniMax from environment."""
from __future__ import annotations

import os
from crewai import LLM

# Cached LLM instances per model name
_llm_cache: dict[str, LLM] = {}


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
    _llm_cache[model] = llm
    return llm


def get_ollama_embedder_config() -> dict:
    """Return Ollama embedder config dict for CrewAI memory."""
    from sentinel_v2.config.embedder_config import get_ollama_embedder_config as _get
    return _get()