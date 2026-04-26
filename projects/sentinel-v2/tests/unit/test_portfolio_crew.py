"""Tests for sentinel_v2.crews.portfolio_crew."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

_MODULE = "sentinel_v2.crews.portfolio_crew.portfolio_crew"


def _patches():
    """Return a dict of patches that make the crew factory callable without real LLMs."""
    return {
        f"{_MODULE}.Agent": patch(f"{_MODULE}.Agent"),
        f"{_MODULE}.Crew": patch(f"{_MODULE}.Crew"),
        f"{_MODULE}.Task": patch(f"{_MODULE}.Task"),
        f"{_MODULE}.get_minimax_llm": patch(f"{_MODULE}.get_minimax_llm", return_value=MagicMock()),
        f"{_MODULE}.get_memory_for_crew_full": patch(f"{_MODULE}.get_memory_for_crew_full", return_value=MagicMock()),
        f"{_MODULE}.hook_crew_full": patch(f"{_MODULE}.hook_crew_full", side_effect=lambda crew, **kw: crew),
        f"{_MODULE}.ListFilesTool": patch(f"{_MODULE}.ListFilesTool"),
        f"{_MODULE}.WriteFileTool": patch(f"{_MODULE}.WriteFileTool"),
    }


class TestPortfolioCrew:
    """Tests for portfolio_crew() factory."""

    def test_crew_has_one_agent_and_one_task(self):
        patches = _patches()
        mocks = {k: p.start() for k, p in patches.items()}
        try:
            from sentinel_v2.crews.portfolio_crew import portfolio_crew
            portfolio_crew(cycle=1)

            mock_agent = mocks[f"{_MODULE}.Agent"]
            mock_task = mocks[f"{_MODULE}.Task"]
            mock_crew = mocks[f"{_MODULE}.Crew"]

            assert mock_agent.call_count == 1
            assert mock_task.call_count == 1
            crew_kwargs = mock_crew.call_args.kwargs
            assert len(crew_kwargs["agents"]) == 1
            assert len(crew_kwargs["tasks"]) == 1

            agent_kwargs = mock_agent.call_args.kwargs
            assert agent_kwargs["role"] == "Portfolio Maintainer"
        finally:
            for p in patches.values():
                p.stop()

    def test_hooks_applied(self):
        patches = _patches()
        mocks = {k: p.start() for k, p in patches.items()}
        try:
            from sentinel_v2.crews.portfolio_crew import portfolio_crew
            portfolio_crew(cycle=3)

            mock_hook = mocks[f"{_MODULE}.hook_crew_full"]
            mock_hook.assert_called_once()
            _, kwargs = mock_hook.call_args
            assert kwargs["phase"] == "portfolio"
            assert kwargs["cycle"] == 3
        finally:
            for p in patches.values():
                p.stop()

    def test_agent_has_file_tools(self):
        patches = _patches()
        mocks = {k: p.start() for k, p in patches.items()}
        try:
            from sentinel_v2.crews.portfolio_crew import portfolio_crew
            portfolio_crew()

            agent_kwargs = mocks[f"{_MODULE}.Agent"].call_args.kwargs
            tool_instances = agent_kwargs["tools"]
            assert len(tool_instances) == 2
        finally:
            for p in patches.values():
                p.stop()
