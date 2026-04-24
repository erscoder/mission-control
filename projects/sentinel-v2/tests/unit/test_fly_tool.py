"""Tests for fly_tool.py — flyctl wrapper (subprocess mocked)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from sentinel_v2.tools.fly_tool import (
    FlyAppCreateTool,
    FlyDeployTool,
    FlySecretsSetTool,
    FlyStatusTool,
    _run_flyctl,
)


@pytest.fixture(autouse=True)
def _fly_token(monkeypatch):
    monkeypatch.setenv("FLY_API_TOKEN", "fly_test_123")


def _mock_proc(rc: int = 0, out: str = "", err: str = ""):
    return MagicMock(returncode=rc, stdout=out, stderr=err)


# ── _run_flyctl ──────────────────────────────────────────────────────────────


def test_run_flyctl_returns_binary_not_found_when_missing():
    with patch("sentinel_v2.tools.fly_tool.subprocess.run", side_effect=FileNotFoundError()):
        rc, out = _run_flyctl(["version"])
    assert rc == 127
    assert "not found" in out


def test_run_flyctl_passes_token_in_env():
    mock_run = MagicMock(return_value=_mock_proc(0, "ok", ""))
    with patch("sentinel_v2.tools.fly_tool.subprocess.run", mock_run):
        _run_flyctl(["version"])
    _, kwargs = mock_run.call_args
    assert kwargs["env"]["FLY_API_TOKEN"] == "fly_test_123"


# ── FlyAppCreateTool ─────────────────────────────────────────────────────────


def test_app_create_rejects_invalid_name():
    result = FlyAppCreateTool()._run(app_name="INVALID_UPPER")
    assert "invalid" in result


def test_app_create_reuses_existing():
    existing_apps = json.dumps([{"Name": "myapp"}])
    with patch(
        "sentinel_v2.tools.fly_tool._run_flyctl",
        return_value=(0, existing_apps),
    ):
        result = FlyAppCreateTool()._run(app_name="myapp")
    data = json.loads(result)
    assert data["reused"] is True
    assert data["app_name"] == "myapp"


def test_app_create_creates_new():
    def fake(args, **_):
        if args[:2] == ["apps", "list"]:
            return 0, "[]"
        if args[:2] == ["apps", "create"]:
            return 0, "created"
        return 1, "unknown"

    with patch("sentinel_v2.tools.fly_tool._run_flyctl", side_effect=fake):
        result = FlyAppCreateTool()._run(app_name="newapp")
    data = json.loads(result)
    assert data["reused"] is False
    assert data["app_url"] == "https://newapp.fly.dev"


# ── FlySecretsSetTool ────────────────────────────────────────────────────────


def test_secrets_set_passes_kv_pairs():
    mock = MagicMock(return_value=(0, "Release v2 created"))
    with patch("sentinel_v2.tools.fly_tool._run_flyctl", mock):
        result = FlySecretsSetTool()._run(
            app_name="myapp",
            secrets={"FOO": "bar", "BAZ": "qux"},
        )
    data = json.loads(result)
    assert set(data["set"]) == {"FOO", "BAZ"}
    args = mock.call_args[0][0]
    assert "secrets" in args and "set" in args
    assert "--app" in args and "myapp" in args


def test_secrets_set_empty_is_noop():
    result = FlySecretsSetTool()._run(app_name="myapp", secrets={})
    assert json.loads(result) == {"set": []}


def test_secrets_set_stage_flag():
    mock = MagicMock(return_value=(0, ""))
    with patch("sentinel_v2.tools.fly_tool._run_flyctl", mock):
        FlySecretsSetTool()._run(app_name="myapp", secrets={"K": "v"}, stage=True)
    args = mock.call_args[0][0]
    assert "--stage" in args


# ── FlyDeployTool ────────────────────────────────────────────────────────────


def test_deploy_success_returns_url():
    out = "Deploying\nrelease v3 created\nDone"
    with patch("sentinel_v2.tools.fly_tool._run_flyctl", return_value=(0, out)):
        result = FlyDeployTool()._run(app_name="myapp", source_dir="/tmp/ws")
    data = json.loads(result)
    assert data["url"] == "https://myapp.fly.dev"
    assert data["version"] == 3


def test_deploy_failure_returns_error():
    with patch("sentinel_v2.tools.fly_tool._run_flyctl", return_value=(1, "build error")):
        result = FlyDeployTool()._run(app_name="myapp", source_dir="/tmp/ws")
    assert result.startswith("error rc=1")


# ── FlyStatusTool ────────────────────────────────────────────────────────────


def test_status_returns_parsed_json():
    status_json = '{"Status":"running","Machines":[]}'
    with patch("sentinel_v2.tools.fly_tool._run_flyctl", return_value=(0, status_json)):
        result = FlyStatusTool()._run(app_name="myapp")
    parsed = json.loads(result)
    assert parsed["Status"] == "running"


# ── Missing env var ──────────────────────────────────────────────────────────


def test_missing_fly_token_raises(monkeypatch):
    monkeypatch.delenv("FLY_API_TOKEN", raising=False)
    from sentinel_v2.tools.fly_tool import _fly_env
    with pytest.raises(RuntimeError, match="FLY_API_TOKEN"):
        _fly_env()
