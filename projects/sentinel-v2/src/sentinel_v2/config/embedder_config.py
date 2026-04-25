"""Embedder configuration — Jina AI for lightweight embeddings."""
from __future__ import annotations

import os
from pathlib import Path


def _load_env():
    """Load .env file from project root."""
    env_file = Path(__file__).parent.parent.parent / '.env'
    if env_file.exists():
        # Simple line-by-line parser (no external dotenv dependency)
        for line in env_file.read_text().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()


# Load .env on module import
_load_env()


def get_jina_embedder_config() -> dict:
    """
    Return Jina AI embedder config dict for CrewAI memory.

    Jina AI provides lightweight, fast embeddings with a free tier (100K tokens/month).
    Much more efficient than local Ollama models.

    Usage in Crew:
        Crew(..., embedder=get_jina_embedder_config())

    Usage in Memory:
        Memory(embedder=get_jina_embedder_config())
    """
    jina_api_key = os.environ.get("JINA_API_KEY")
    if not jina_api_key:
        # Fallback to OpenAI if Jina key not set
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            return {
                "provider": "openai",
                "config": {
                    "api_key": openai_key,
                    "model_name": "text-embedding-3-small",
                },
            }
        # Final fallback to Ollama (not recommended)
        return {
            "provider": "ollama",
            "config": {
                "model_name": os.environ.get(
                    "OLLAMA_EMBED_MODEL", "locusai/all-minilm-l6-v2"
                ),
                "url": os.environ.get(
                    "OLLAMA_URL", "http://localhost:11434"
                ) + "/api/embeddings",
            },
        }

    return {
        "provider": "jina",
        "config": {
            "api_key": jina_api_key,
            "model_name": "jina-embeddings-v3",
        },
    }


def get_memory_for_crew(llm=None):
    """
    Return a CrewAI Memory instance configured for Jina embeddings + MiniMax LLM.

    Args:
        llm: LLM instance to use for memory analysis (defaults to MiniMax if None)

    Usage:
        from sentinel_v2.config.embedder_config import get_memory_for_crew
        Crew(..., memory=get_memory_for_crew(minimax_llm))
    """
    from crewai.memory.unified_memory import Memory

    from sentinel_v2.config.llm_config import get_minimax_llm, make_clean_llm
    if llm is None:
        llm = get_minimax_llm()
    make_clean_llm(llm)  # idempotent — wraps whether caller passed one or not

    return Memory(
        llm=llm,
        embedder=get_jina_embedder_config(),
    )


def get_memory_for_crew_full(minimax_llm):
    """
    Return a CrewAI Memory instance, or None if memory is disabled.

    Memory is DISABLED by default (returns None) because CrewAI's UnifiedMemory
    layer uses LiteLLM structured outputs (instructor / response_format=QueryAnalysis)
    which BYPASSES our `llm.call()` <think>-stripping wrapper. With MiniMax reasoning
    models that prepend <think>...</think>, this consistently fails with
    "Invalid JSON: expected value at line 1 column 1" and the embedder defaults
    to OpenAI which then complains about CHROMA_OPENAI_API_KEY.

    Set SENTINEL_ENABLE_MEMORY=1 to opt back in (you'll need a non-reasoning
    LLM and a working embedder).
    """
    if os.environ.get("SENTINEL_ENABLE_MEMORY") == "1":
        return get_memory_for_crew(llm=minimax_llm)
    return None
