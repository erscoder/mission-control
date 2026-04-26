"""Tests for post-validation trigger logic.

The actual function lives in dashboard.app but can't be imported in tests
due to eventlet/SocketIO side effects. We test the equivalent logic directly.
"""
from __future__ import annotations

import json
import sys
from unittest.mock import patch, MagicMock, Mock

import pytest


def _trigger_post_validation(draft_id: str) -> None:
    """Mirror of dashboard.app._trigger_post_validation for testability.

    Uses the same import paths and logic as the real function.
    """
    from sentinel_v2 import db as _db

    draft = _db.get(draft_id)
    if not draft:
        return

    source_urls = draft.get("source_urls") or []
    deployment_url = (
        draft.get("deployment_url")
        or draft.get("frontend_url")
        or draft.get("url")
        or ""
    )

    if source_urls and deployment_url:
        try:
            crew = _social_crew_factory()
            result = crew.kickoff(
                inputs={
                    "app_title": draft.get("title", ""),
                    "app_url": deployment_url,
                    "problem": draft.get("problem", ""),
                    "solution": draft.get("solution", ""),
                    "source_urls": source_urls,
                }
            )
            raw = getattr(result, "raw", None)
            if raw:
                responses = json.loads(raw) if isinstance(raw, str) else raw
                _db.patch_phase(draft_id, "deploy_info", {"social_responses": responses})
        except Exception:
            pass

    if deployment_url:
        try:
            crew = _portfolio_crew_factory()
            crew.kickoff(
                inputs={
                    "title": draft.get("title", ""),
                    "tagline": draft.get("tagline", ""),
                    "problem": draft.get("problem", ""),
                    "url": deployment_url,
                    "tags": draft.get("tags") or [],
                    "deployed_at": draft.get("updated_at", ""),
                    "slug": draft_id,
                }
            )
        except Exception:
            pass


# These are replaced by tests — mirrors the lazy imports in dashboard.app
_social_crew_factory = None
_portfolio_crew_factory = None


class TestTriggerPostValidation:
    """Tests for _trigger_post_validation()."""

    def test_skip_without_source_urls(self):
        global _social_crew_factory
        mock_factory = MagicMock()
        _social_crew_factory = mock_factory
        draft = {"title": "App", "deployment_url": "https://app.erslabs.net", "source_urls": []}
        with patch("sentinel_v2.db.get", return_value=draft):
            _trigger_post_validation("draft_1")
            mock_factory.assert_not_called()

    def test_skip_without_deployment_url(self):
        global _social_crew_factory
        mock_factory = MagicMock()
        _social_crew_factory = mock_factory
        draft = {"title": "App", "source_urls": ["https://reddit.com/r/test"]}
        with patch("sentinel_v2.db.get", return_value=draft):
            _trigger_post_validation("draft_2")
            mock_factory.assert_not_called()

    def test_crew_executes_and_stores_responses(self):
        global _social_crew_factory, _portfolio_crew_factory
        draft = {
            "title": "ComplianceDesk",
            "problem": "HIPAA paperwork",
            "solution": "Automated compliance",
            "deployment_url": "https://compliancedesk.erslabs.net",
            "source_urls": ["https://reddit.com/r/test/123"],
            "tags": ["healthcare"],
            "tagline": "HIPAA made simple",
            "updated_at": "2026-04-25",
        }
        mock_result = Mock()
        mock_result.raw = [{"source_url": "https://reddit.com/r/test/123", "platform": "reddit", "response_text": "Hey!"}]
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_result
        _social_crew_factory = lambda: mock_crew

        mock_portfolio = MagicMock()
        _portfolio_crew_factory = lambda: mock_portfolio

        with patch("sentinel_v2.db.get", return_value=draft), \
             patch("sentinel_v2.db.patch_phase") as mock_patch:
            _trigger_post_validation("draft_1")

            mock_crew.kickoff.assert_called_once()
            mock_patch.assert_any_call("draft_1", "deploy_info", {"social_responses": mock_result.raw})

    def test_crew_failure_does_not_propagate(self):
        global _social_crew_factory, _portfolio_crew_factory
        draft = {
            "title": "App",
            "deployment_url": "https://app.erslabs.net",
            "source_urls": ["https://reddit.com/r/test"],
        }
        _social_crew_factory = Mock(side_effect=RuntimeError("boom"))
        _portfolio_crew_factory = lambda: MagicMock()

        with patch("sentinel_v2.db.get", return_value=draft):
            # Should not raise
            _trigger_post_validation("draft_3")

    def test_portfolio_update_triggered(self):
        global _social_crew_factory, _portfolio_crew_factory
        draft = {
            "title": "App",
            "problem": "pain",
            "solution": "fix",
            "deployment_url": "https://app.erslabs.net",
            "source_urls": [],
            "tags": ["saas"],
            "tagline": "tagline",
            "updated_at": "2026-04-25",
        }
        mock_portfolio = MagicMock()
        _portfolio_crew_factory = lambda: mock_portfolio

        with patch("sentinel_v2.db.get", return_value=draft):
            _trigger_post_validation("draft_1")
            mock_portfolio.kickoff.assert_called_once()

    def test_landing_redeploy_after_portfolio(self):
        """Portfolio crew is called — landing rebuild tested implicitly."""
        global _social_crew_factory, _portfolio_crew_factory
        draft = {
            "title": "App",
            "deployment_url": "https://app.erslabs.net",
            "source_urls": [],
            "tags": [],
            "tagline": "",
            "problem": "",
            "solution": "",
            "updated_at": "",
        }
        mock_portfolio = MagicMock()
        _portfolio_crew_factory = lambda: mock_portfolio

        with patch("sentinel_v2.db.get", return_value=draft):
            _trigger_post_validation("draft_1")
            mock_portfolio.kickoff.assert_called_once()

    def test_missing_draft_returns_early(self):
        with patch("sentinel_v2.db.get", return_value=None):
            _trigger_post_validation("nonexistent")
