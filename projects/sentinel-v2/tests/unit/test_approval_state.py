"""
Unit tests for sentinel_v2/tools/approval_state.py
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import pytest
from sentinel_v2.tools.approval_state import ApprovalState


@pytest.fixture
def state_file():
    """Unique temp file per test."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def approval(state_file):
    return ApprovalState(path=state_file)


class TestApprovalState:
    """Tests for ApprovalState."""

    def test_set_and_is_approved(self, approval):
        """Pending → approved → is_approved returns True."""
        approval.set_pending(cycle=1, summary="draft v1")
        assert not approval.is_approved(1)

        approval.set_approved(1)
        assert approval.is_approved(1)

    def test_set_pending_then_approved_different_cycle(self, approval):
        """Approving a different cycle doesn't affect another."""
        approval.set_pending(cycle=1, summary="draft v1")
        approval.set_approved(2)
        assert not approval.is_approved(1)

    def test_revision_requested(self, approval):
        """Revision requested → is_revison_requested returns True."""
        approval.set_pending(cycle=3, summary="draft v3")
        approval.set_revision(3, notes="Make it simpler")
        assert approval.is_revison_requested(3)
        assert not approval.is_approved(3)

    def test_stop_requested(self, approval):
        """Stop requested → is_stop_requested returns True."""
        approval.set_pending(cycle=1, summary="draft")
        approval.set_stop()
        assert approval.is_stop_requested()

    def test_get_action(self, approval):
        """get_action returns the correct action string."""
        approval.set_pending(cycle=1, summary="draft")
        assert approval.get_action(1) is None

        approval.set_approved(1)
        assert approval.get_action(1) == "approved"

        approval.set_pending(cycle=2, summary="draft2")
        approval.set_revision(2, notes="nope")
        assert approval.get_action(2) == "revision"

    def test_clear_pending(self, approval):
        """clear_pending removes only that cycle's pending state."""
        approval.set_pending(cycle=1, summary="draft1")
        approval.set_pending(cycle=2, summary="draft2")
        approval.set_approved(1)

        approval.clear_pending(1)
        # Cycle 2 should still be pending
        assert not approval.is_approved(2)

    def test_clear_all(self, approval):
        """clear_all removes all state."""
        approval.set_pending(cycle=1, summary="draft1")
        approval.set_stop()
        approval.clear_all()

        assert not approval.is_approved(1)
        assert not approval.is_stop_requested()

    def test_auto_approved(self, approval):
        """set_auto_approved marks a cycle as approved without Telegram."""
        approval.set_auto_approved(cycle=5)
        assert approval.is_approved(5)
        assert approval.get_action(5) == "auto_approved"

    def test_concurrent_write_safe(self, approval):
        """Thread-safe writes don't corrupt state."""
        errors = []

        def writer(cycle_start):
            try:
                for i in range(10):
                    approval.set_pending(cycle=cycle_start + i, summary=f"draft {i}")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer, args=(1,))
        t2 = threading.Thread(target=writer, args=(11,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        # File should still be valid JSON
        if os.path.exists(approval._path):
            data = json.loads(open(approval._path).read())
            assert isinstance(data, dict)

    def test_timeout_auto_approves(self, approval, monkeypatch):
        """If timeout is reached, is_approved returns True (auto-approve)."""
        import datetime

        approval.set_pending(cycle=1, summary="draft", timeout_seconds=0)

        # Manually set timeout to the past
        with open(approval._path, "w") as f:
            json.dump(
                {
                    "pending": {
                        "cycle": 1,
                        "summary": "draft",
                        "timeout_at": "2020-01-01T00:00:00+00:00",
                        "action": None,
                    }
                },
                f,
            )

        assert approval.is_approved(1)
