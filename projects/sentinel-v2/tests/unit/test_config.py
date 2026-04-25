"""Tests for sentinel_v2.config.llm_config and embedder_config."""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Path setup — add src/ to sys.path
# ---------------------------------------------------------------------------

SRC_ROOT = Path(__file__).parent.parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_llm_cache():
    """Clear the LLM cache between tests.

    Uses sys.modules to access the already-imported module without re-triggering
    __init__.py imports (which would re-import crewai and hit numpy conflicts).
    """
    mod = sys.modules.get("sentinel_v2.config.llm_config")
    if mod is not None:
        mod._llm_cache.clear()


# ---------------------------------------------------------------------------
# llm_config — get_minimax_llm
# ---------------------------------------------------------------------------

class TestGetMiniMaxLLM:
    """Tests for get_minimax_llm."""

    def setup_method(self):
        # Other tests in the suite may have populated the module-level cache
        # (e.g., integration tests exercising the crews). Clear before each test
        # so the key-missing path is actually reachable.
        _reset_llm_cache()

    def teardown_method(self):
        _reset_llm_cache()

    def test_raises_when_api_key_missing(self):
        """Raises RuntimeError when MINIMAX_API_KEY is not set.

        We mock os.environ.get to simulate the missing key without needing to
        manipulate the real environment (crewai loads .env on import).
        """
        from sentinel_v2.config.llm_config import get_minimax_llm

        original_get = os.environ.get

        def fake_get(key, default=None):
            if key == "MINIMAX_API_KEY":
                return None
            if key == "MINIMAX_BASE_URL":
                return original_get(key, default)
            return original_get(key, default)

        with patch.object(os.environ, "get", fake_get):
            with pytest.raises(RuntimeError, match="MINIMAX_API_KEY not set"):
                get_minimax_llm()

    def test_uses_env_variables(self, monkeypatch):
        """Reads MINIMAX_API_KEY and MINIMAX_BASE_URL from env."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-123")
        monkeypatch.setenv("MINIMAX_BASE_URL", "https://custom.minimax.io/v1")
        from sentinel_v2.config.llm_config import get_minimax_llm
        llm = get_minimax_llm("MiniMax-M2.7")
        assert llm is not None
        assert llm.model == "MiniMax-M2.7"
        assert llm.api_key == "test-key-123"
        assert llm.base_url == "https://custom.minimax.io/v1"

    def test_defaults_base_url_when_not_set(self, monkeypatch):
        """Uses default base URL when MINIMAX_BASE_URL is not set."""
        monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-456")
        from sentinel_v2.config.llm_config import get_minimax_llm
        llm = get_minimax_llm()
        assert llm.base_url == "https://api.minimax.io/v1"

    def test_cached_instance_returned_on_second_call(self, monkeypatch):
        """Second call with same model returns the cached LLM instance."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-cache")
        from sentinel_v2.config.llm_config import get_minimax_llm
        llm1 = get_minimax_llm("MiniMax-M2.7")
        llm2 = get_minimax_llm("MiniMax-M2.7")
        assert llm1 is llm2  # Same object reference

    def test_different_models_get_different_instances(self, monkeypatch):
        """Different model names produce different LLM instances."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-diff")
        from sentinel_v2.config.llm_config import get_minimax_llm
        llm1 = get_minimax_llm("MiniMax-M2.7")
        llm2 = get_minimax_llm("MiniMax-Other")
        assert llm1 is not llm2
        assert llm1.model == "MiniMax-M2.7"
        assert llm2.model == "MiniMax-Other"


# ---------------------------------------------------------------------------
# llm_config — get_ollama_embedder_config
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# embedder_config — get_jina_embedder_config fallback paths
# ---------------------------------------------------------------------------

class TestGetJinaEmbedderConfig:
    """Tests for get_jina_embedder_config."""

    def _with_keys(self, jina_key=None, openai_key=None, ollama_model=None, ollama_url=None):
        """Set env keys for a specific test scenario."""
        for k in ("JINA_API_KEY", "OPENAI_API_KEY", "OLLAMA_EMBED_MODEL", "OLLAMA_URL"):
            os.environ.pop(k, None)
        if jina_key is not None:
            os.environ["JINA_API_KEY"] = jina_key
        if openai_key is not None:
            os.environ["OPENAI_API_KEY"] = openai_key
        if ollama_model is not None:
            os.environ["OLLAMA_EMBED_MODEL"] = ollama_model
        if ollama_url is not None:
            os.environ["OLLAMA_URL"] = ollama_url

    def test_jina_provider_when_key_set(self):
        """Returns Jina config when JINA_API_KEY is set."""
        self._with_keys(jina_key="jina-test-key")
        from sentinel_v2.config.embedder_config import get_jina_embedder_config
        config = get_jina_embedder_config()
        assert config["provider"] == "jina"
        assert config["config"]["api_key"] == "jina-test-key"
        assert config["config"]["model_name"] == "jina-embeddings-v3"

    def test_fallback_to_openai_when_no_jina_key(self):
        """Falls back to OpenAI when JINA_API_KEY is missing but OPENAI_API_KEY is set."""
        self._with_keys(openai_key="openai-test-key")
        from sentinel_v2.config.embedder_config import get_jina_embedder_config
        config = get_jina_embedder_config()
        assert config["provider"] == "openai"
        assert config["config"]["api_key"] == "openai-test-key"
        assert config["config"]["model_name"] == "text-embedding-3-small"

    def test_fallback_to_ollama_when_no_jina_or_openai_key(self):
        """Falls back to Ollama when neither JINA nor OpenAI keys are set."""
        self._with_keys(ollama_model="custom-embed-model", ollama_url="http://custom:11434")
        from sentinel_v2.config.embedder_config import get_jina_embedder_config
        config = get_jina_embedder_config()
        assert config["provider"] == "ollama"
        assert config["config"]["model_name"] == "custom-embed-model"
        assert "custom:11434" in config["config"]["url"]

    def test_ollama_fallback_uses_default_model(self):
        """Uses default Ollama model when OLLAMA_EMBED_MODEL is not set."""
        self._with_keys()
        from sentinel_v2.config.embedder_config import get_jina_embedder_config
        config = get_jina_embedder_config()
        assert config["provider"] == "ollama"
        assert config["config"]["model_name"] == "locusai/all-minilm-l6-v2"

    def test_ollama_fallback_uses_default_url(self):
        """Uses default Ollama URL when OLLAMA_URL is not set."""
        self._with_keys()
        from sentinel_v2.config.embedder_config import get_jina_embedder_config
        config = get_jina_embedder_config()
        assert config["provider"] == "ollama"
        assert config["config"]["url"] == "http://localhost:11434/api/embeddings"


# ---------------------------------------------------------------------------
# embedder_config — get_memory_for_crew
# ---------------------------------------------------------------------------

class TestGetMemoryForCrew:
    """Tests for get_memory_for_crew."""

    def teardown_method(self):
        _reset_llm_cache()

    def test_returns_memory_instance(self, monkeypatch):
        """Returns a CrewAI Memory instance."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-mem")
        monkeypatch.setenv("JINA_API_KEY", "jina-key-for-mem")
        from sentinel_v2.config.embedder_config import get_memory_for_crew
        memory = get_memory_for_crew()
        assert memory is not None

    def test_uses_provided_llm(self, monkeypatch):
        """Uses the LLM passed as argument instead of creating one."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-mem2")
        from sentinel_v2.config.llm_config import get_minimax_llm
        llm = get_minimax_llm()
        from sentinel_v2.config.embedder_config import get_memory_for_crew
        memory = get_memory_for_crew(llm=llm)
        assert memory is not None


# ---------------------------------------------------------------------------
# embedder_config — get_memory_for_crew_full
# ---------------------------------------------------------------------------

class TestGetMemoryForCrewFull:
    """Tests for get_memory_for_crew_full."""

    def teardown_method(self):
        _reset_llm_cache()

    def test_returns_none_by_default(self, monkeypatch):
        """Memory is disabled by default to dodge MiniMax <think> JSON parse failures."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-full")
        monkeypatch.setenv("JINA_API_KEY", "jina-key-full")
        monkeypatch.delenv("SENTINEL_ENABLE_MEMORY", raising=False)
        from sentinel_v2.config.llm_config import get_minimax_llm
        from sentinel_v2.config.embedder_config import get_memory_for_crew_full
        llm = get_minimax_llm()
        memory = get_memory_for_crew_full(llm)
        assert memory is None

    def test_returns_memory_instance_when_enabled(self, monkeypatch):
        """SENTINEL_ENABLE_MEMORY=1 opts back into the (broken-with-reasoning-LLMs) memory path."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-full")
        monkeypatch.setenv("JINA_API_KEY", "jina-key-full")
        monkeypatch.setenv("SENTINEL_ENABLE_MEMORY", "1")
        from sentinel_v2.config.llm_config import get_minimax_llm
        from sentinel_v2.config.embedder_config import get_memory_for_crew_full
        llm = get_minimax_llm()
        memory = get_memory_for_crew_full(llm)
        assert memory is not None
