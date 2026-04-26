"""Tests for sentinel_v2.crews.social_response_crew."""
from __future__ import annotations

from unittest.mock import patch, MagicMock, call

_MODULE = "sentinel_v2.crews.social_response_crew.social_response_crew"


def _patches():
    """Return a dict of patches that make the crew factory callable without real LLMs."""
    return {
        f"{_MODULE}.Agent": patch(f"{_MODULE}.Agent"),
        f"{_MODULE}.Crew": patch(f"{_MODULE}.Crew"),
        f"{_MODULE}.Task": patch(f"{_MODULE}.Task"),
        f"{_MODULE}.get_minimax_llm": patch(f"{_MODULE}.get_minimax_llm", return_value=MagicMock()),
        f"{_MODULE}.get_memory_for_crew_full": patch(f"{_MODULE}.get_memory_for_crew_full", return_value=MagicMock()),
        f"{_MODULE}.hook_crew_full": patch(f"{_MODULE}.hook_crew_full", side_effect=lambda crew, **kw: crew),
    }


class TestSocialResponseCrew:
    """Tests for social_response_crew() factory."""

    def test_crew_has_one_agent_and_one_task(self):
        patches = _patches()
        mocks = {k: p.start() for k, p in patches.items()}
        try:
            from sentinel_v2.crews.social_response_crew import social_response_crew
            social_response_crew(cycle=1)

            mock_agent = mocks[f"{_MODULE}.Agent"]
            mock_task = mocks[f"{_MODULE}.Task"]
            mock_crew = mocks[f"{_MODULE}.Crew"]

            assert mock_agent.call_count == 1
            assert mock_task.call_count == 1
            # Crew called with agents list of length 1 and tasks list of length 1
            crew_kwargs = mock_crew.call_args.kwargs
            assert len(crew_kwargs["agents"]) == 1
            assert len(crew_kwargs["tasks"]) == 1

            # Agent role check
            agent_kwargs = mock_agent.call_args.kwargs
            assert agent_kwargs["role"] == "Social Response Specialist"
        finally:
            for p in patches.values():
                p.stop()

    def test_hooks_applied(self):
        patches = _patches()
        mocks = {k: p.start() for k, p in patches.items()}
        try:
            from sentinel_v2.crews.social_response_crew import social_response_crew
            social_response_crew(cycle=5)

            mock_hook = mocks[f"{_MODULE}.hook_crew_full"]
            mock_hook.assert_called_once()
            _, kwargs = mock_hook.call_args
            assert kwargs["phase"] == "social_response"
            assert kwargs["cycle"] == 5
        finally:
            for p in patches.values():
                p.stop()
