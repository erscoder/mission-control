"""Tests for sentinel_v2.dashboard_state module."""
import pytest
import json
from pathlib import Path
from unittest.mock import mock_open, patch, MagicMock
from datetime import datetime, timezone

from sentinel_v2.dashboard_state import (
    write_state,
    add_agent_message,
    get_agent_messages,
    clear_agent_messages,
    STATE_FILE,
    AGENT_MESSAGES_FILE,
)


class TestWriteState:
    """Test write_state function."""

    def test_write_state_creates_file(self, monkeypatch, tmp_path):
        """write_state creates state file with correct data."""
        state_file = tmp_path / "state.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.STATE_FILE", state_file)

        write_state(
            cycle=5,
            phase="research",
            opportunity={"title": "Test SaaS"},
            match_score=0.85,
            deployed=False,
        )

        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["cycle"] == 5
        assert data["phase"] == "research"
        assert data["opportunity"] == {"title": "Test SaaS"}
        assert data["match_score"] == 0.85
        assert data["deployed"] is False
        assert "updated_at" in data

    def test_write_state_with_none_values(self, monkeypatch, tmp_path):
        """write_state handles None opportunity and build_output."""
        state_file = tmp_path / "state.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.STATE_FILE", state_file)

        write_state(
            cycle=1,
            phase="idle",
            opportunity=None,
            build_output=None,
            match_score=0.0,
            deployed=False,
        )

        data = json.loads(state_file.read_text())
        assert data["opportunity"] is None
        assert data["build_output"] is None

    def test_write_state_updates_existing_file(self, monkeypatch, tmp_path):
        """write_state overwrites previous state."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"cycle": 1, "phase": "old"}')
        monkeypatch.setattr("sentinel_v2.dashboard_state.STATE_FILE", state_file)

        write_state(cycle=99, phase="new", opportunity=None, match_score=0.5, deployed=True)

        data = json.loads(state_file.read_text())
        assert data["cycle"] == 99
        assert data["phase"] == "new"

    def test_write_state_handles_file_write_error(self, monkeypatch, tmp_path):
        """write_state handles exceptions gracefully (doesn't crash)."""
        state_file = tmp_path / "state.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.STATE_FILE", state_file)

        # Make open() raise
        with patch("builtins.open", side_effect=OSError("disk full")):
            # Should not raise
            write_state(cycle=1, phase="test", opportunity=None, match_score=0.0, deployed=False)

    def test_write_state_includes_timestamp(self, monkeypatch, tmp_path):
        """write_state includes ISO timestamp."""
        state_file = tmp_path / "state.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.STATE_FILE", state_file)

        write_state(cycle=1, phase="research", opportunity=None, match_score=0.0, deployed=False)

        data = json.loads(state_file.read_text())
        assert "updated_at" in data
        # Should be valid ISO format
        datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))


class TestAddAgentMessage:
    """Test add_agent_message function."""

    def test_add_agent_message_creates_file(self, monkeypatch, tmp_path):
        """add_agent_message creates messages file."""
        msgs_file = tmp_path / "messages.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        add_agent_message(
            agent_id="web-scout",
            message="Found opportunity: AI code reviewer",
            metadata={"source": "hackernews"},
            cycle=3,
        )

        assert msgs_file.exists()
        msgs = json.loads(msgs_file.read_text())
        assert len(msgs) == 1
        assert msgs[0]["agent_id"] == "web-scout"
        assert msgs[0]["message"] == "Found opportunity: AI code reviewer"
        assert msgs[0]["metadata"] == {"source": "hackernews"}
        assert msgs[0]["cycle"] == 3

    def test_add_agent_message_appends_to_existing(self, monkeypatch, tmp_path):
        """add_agent_message appends to existing messages."""
        msgs_file = tmp_path / "messages.json"
        msgs_file.write_text(json.dumps([
            {"agent_id": "old-agent", "message": "old msg", "metadata": {}, "cycle": 1, "timestamp": "2026-01-01T00:00:00Z"}
        ]))
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        add_agent_message(agent_id="new-agent", message="new msg", metadata=None, cycle=2)

        msgs = json.loads(msgs_file.read_text())
        assert len(msgs) == 2
        assert msgs[0]["agent_id"] == "old-agent"
        assert msgs[1]["agent_id"] == "new-agent"

    def test_add_agent_message_trims_to_100(self, monkeypatch, tmp_path):
        """add_agent_message keeps only last 100 messages."""
        msgs_file = tmp_path / "messages.json"
        # Write 105 existing messages
        existing = [{"agent_id": f"agent-{i}", "message": f"msg-{i}", "metadata": {}, "cycle": 1, "timestamp": "2026-01-01T00:00:00Z"} for i in range(105)]
        msgs_file.write_text(json.dumps(existing))
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        add_agent_message(agent_id="new", message="new msg", metadata=None, cycle=2)

        msgs = json.loads(msgs_file.read_text())
        assert len(msgs) == 100
        # Last message should be the new one
        assert msgs[-1]["agent_id"] == "new"
        # First message should be agent-5 (since we had 0-104 plus new = 106, keep last 100 = 6-105 + new)
        assert msgs[0]["agent_id"] == "agent-6"

    def test_add_agent_message_handles_corrupted_file(self, monkeypatch, tmp_path):
        """add_agent_message handles corrupted JSON gracefully."""
        msgs_file = tmp_path / "messages.json"
        msgs_file.write_text("not valid json{{{")
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        # Should not crash, should start fresh
        add_agent_message(agent_id="test", message="msg", metadata=None, cycle=1)

        msgs = json.loads(msgs_file.read_text())
        assert len(msgs) == 1
        assert msgs[0]["agent_id"] == "test"

    def test_add_agent_message_handles_file_write_error(self, monkeypatch, tmp_path):
        """add_agent_message handles write errors gracefully."""
        msgs_file = tmp_path / "messages.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        with patch("builtins.open", side_effect=OSError("disk full")):
            # Should not crash
            add_agent_message(agent_id="test", message="msg", metadata=None, cycle=1)

    def test_add_agent_message_default_cycle_none(self, monkeypatch, tmp_path):
        """add_agent_message defaults cycle to None."""
        msgs_file = tmp_path / "messages.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        add_agent_message(agent_id="test", message="msg")

        msgs = json.loads(msgs_file.read_text())
        assert msgs[0]["cycle"] is None

    def test_add_agent_message_default_metadata_empty(self, monkeypatch, tmp_path):
        """add_agent_message defaults metadata to empty dict."""
        msgs_file = tmp_path / "messages.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        add_agent_message(agent_id="test", message="msg")

        msgs = json.loads(msgs_file.read_text())
        assert msgs[0]["metadata"] == {}


class TestGetAgentMessages:
    """Test get_agent_messages function."""

    def test_get_agent_messages_returns_list(self, monkeypatch, tmp_path):
        """get_agent_messages returns parsed JSON list."""
        msgs_file = tmp_path / "messages.json"
        msgs_file.write_text(json.dumps([
            {"agent_id": "a1", "message": "m1", "metadata": {}, "cycle": 1, "timestamp": "2026-01-01T00:00:00Z"},
            {"agent_id": "a2", "message": "m2", "metadata": {}, "cycle": 2, "timestamp": "2026-01-02T00:00:00Z"},
        ]))
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        result = get_agent_messages()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["agent_id"] == "a1"
        assert result[1]["agent_id"] == "a2"

    def test_get_agent_messages_empty_when_file_missing(self, monkeypatch, tmp_path):
        """get_agent_messages returns empty list if file doesn't exist."""
        msgs_file = tmp_path / "messages.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        result = get_agent_messages()

        assert result == []

    def test_get_agent_messages_handles_corrupted_file(self, monkeypatch, tmp_path):
        """get_agent_messages handles corrupted JSON gracefully."""
        msgs_file = tmp_path / "messages.json"
        msgs_file.write_text("not valid json{{{")
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        result = get_agent_messages()

        assert result == []

    def test_get_agent_messages_handles_read_error(self, monkeypatch, tmp_path):
        """get_agent_messages handles read exceptions gracefully."""
        msgs_file = tmp_path / "messages.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        with patch("builtins.open", side_effect=OSError("permission denied")):
            result = get_agent_messages()

        assert result == []


class TestClearAgentMessages:
    """Test clear_agent_messages function."""

    def test_clear_empties_existing_messages(self, monkeypatch, tmp_path):
        """clear_agent_messages resets the file to an empty list."""
        msgs_file = tmp_path / "messages.json"
        msgs_file.write_text(json.dumps([
            {"agent_id": "a1", "message": "m1", "metadata": {}, "cycle": 1, "timestamp": "t"},
            {"agent_id": "a2", "message": "m2", "metadata": {}, "cycle": 1, "timestamp": "t"},
        ]))
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        clear_agent_messages()

        msgs = json.loads(msgs_file.read_text())
        assert msgs == []

    def test_clear_creates_empty_file_when_missing(self, monkeypatch, tmp_path):
        """clear_agent_messages creates an empty-list file if none exists."""
        msgs_file = tmp_path / "messages.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        clear_agent_messages()

        assert msgs_file.exists()
        msgs = json.loads(msgs_file.read_text())
        assert msgs == []

    def test_clear_does_not_crash_on_error(self, monkeypatch, tmp_path):
        """clear_agent_messages swallows exceptions."""
        msgs_file = tmp_path / "messages.json"
        monkeypatch.setattr("sentinel_v2.dashboard_state.AGENT_MESSAGES_FILE", msgs_file)

        with patch("builtins.open", side_effect=OSError("disk full")):
            clear_agent_messages()  # should not raise


class TestFilesPaths:
    """Test that file paths are correct."""

    def test_state_file_path(self):
        """STATE_FILE points to correct location."""
        from sentinel_v2.dashboard_state import STATE_FILE
        assert STATE_FILE == Path("/tmp/sentinel_v2_state.json")

    def test_agent_messages_file_path(self):
        """AGENT_MESSAGES_FILE points to correct location."""
        from sentinel_v2.dashboard_state import AGENT_MESSAGES_FILE
        assert AGENT_MESSAGES_FILE == Path("/tmp/sentinel_v2_agent_messages.json")