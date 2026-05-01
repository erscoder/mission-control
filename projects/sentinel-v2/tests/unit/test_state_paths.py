"""Tests for the ``resolve_state_path`` helper in ``flows.error_classifier``.

The helper resolves Sentinel state file paths with the following precedence:

  1. ``env_override`` env var (legacy callers).
  2. ``SENTINEL_TMPDIR`` env var (docker-compose volume mount).
  3. ``/tmp`` as last-resort default.

These tests pin that contract so future refactors do not silently regress
the path resolution and reintroduce the F1.1 bug (state files written to
the container's ephemeral overlayfs instead of the mounted volume).
"""
from __future__ import annotations

from pathlib import Path

from sentinel_v2.flows.error_classifier import resolve_state_path


class TestResolveStatePath:
    """Path precedence: env_override > SENTINEL_TMPDIR > /tmp."""

    def test_uses_sentinel_tmpdir_when_set(self, monkeypatch):
        monkeypatch.setenv("SENTINEL_TMPDIR", "/tmp/sentinel_shared")
        monkeypatch.delenv("SENTINEL_ESCALATIONS_FILE", raising=False)

        result = resolve_state_path("sentinel_v2_escalations.json")

        assert result == Path("/tmp/sentinel_shared/sentinel_v2_escalations.json")

    def test_falls_back_to_tmp_when_no_env(self, monkeypatch):
        monkeypatch.delenv("SENTINEL_TMPDIR", raising=False)
        monkeypatch.delenv("SENTINEL_ESCALATIONS_FILE", raising=False)

        result = resolve_state_path("sentinel_v2_state.json")

        assert result == Path("/tmp/sentinel_v2_state.json")

    def test_env_override_wins_over_sentinel_tmpdir(self, monkeypatch):
        monkeypatch.setenv("SENTINEL_TMPDIR", "/tmp/sentinel_shared")
        monkeypatch.setenv(
            "SENTINEL_ESCALATIONS_FILE",
            "/var/data/custom_escalations.json",
        )

        result = resolve_state_path(
            "sentinel_v2_escalations.json",
            env_override="SENTINEL_ESCALATIONS_FILE",
        )

        assert result == Path("/var/data/custom_escalations.json")

    def test_returns_pathlib_path_not_string(self, monkeypatch):
        monkeypatch.setenv("SENTINEL_TMPDIR", "/tmp/sentinel_shared")
        monkeypatch.delenv("SENTINEL_ESCALATIONS_FILE", raising=False)

        result = resolve_state_path("sentinel_v2_escalations.json")

        assert isinstance(result, Path)
