"""Tests for ``_verify_npm_build``.

Trust-but-verify gate that runs after the build crew completes. The QA Lead
self-reports build_status, but a hallucinating LLM can claim 'clean' on a
workspace that won't even ``npm install``. These tests pin the contract so
a future refactor can't quietly turn the gate fail-open again.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from sentinel_v2.flows.sentinel_loop import _verify_npm_build


def _make_workspace(tmp_path: Path, *, with_backend: bool = True,
                    with_frontend: bool = False, backend_pkg: dict | None = None,
                    frontend_pkg: dict | None = None,
                    backend_tsconfig: bool = False) -> Path:
    workspace = tmp_path / "draft_x"
    workspace.mkdir()
    if with_backend:
        backend = workspace / "backend"
        backend.mkdir()
        (backend / "package.json").write_text(
            json.dumps(backend_pkg if backend_pkg is not None
                       else {"name": "b", "scripts": {"build": "echo build"}})
        )
        if backend_tsconfig:
            (backend / "tsconfig.json").write_text("{}")
    if with_frontend:
        frontend = workspace / "frontend"
        frontend.mkdir()
        (frontend / "package.json").write_text(
            json.dumps(frontend_pkg if frontend_pkg is not None
                       else {"name": "f", "scripts": {"build": "echo build"}})
        )
    return workspace


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _fail(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout, stderr=stderr)


class TestVerifyNpmBuild:
    def test_no_subdirs_returns_ok(self, tmp_path: Path):
        # Empty workspace: nothing to verify, both subdirs skipped.
        ws = tmp_path / "empty"
        ws.mkdir()
        with patch("shutil.which", return_value="/usr/bin/npm"):
            result = _verify_npm_build(str(ws))
        assert result["ok"] is True
        assert result["first_failure"] is None
        assert result["details"]["backend"]["skipped"] == "no_directory"
        assert result["details"]["frontend"]["skipped"] == "no_directory"

    def test_npm_missing_short_circuits(self, tmp_path: Path):
        ws = _make_workspace(tmp_path)
        with patch("shutil.which", return_value=None):
            result = _verify_npm_build(str(ws))
        assert result["ok"] is False
        assert result["first_failure"] == "npm_not_found"

    def test_install_failure_marks_backend_install(self, tmp_path: Path):
        ws = _make_workspace(tmp_path)

        def fake_run(cmd, **kwargs):
            assert cmd[1] == "install"
            return _fail(stderr="ERESOLVE peer dep conflict")

        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("subprocess.run", side_effect=fake_run):
            result = _verify_npm_build(str(ws))

        assert result["ok"] is False
        assert result["first_failure"] == "backend.install"
        assert result["details"]["backend"]["install"] == 1
        assert "ERESOLVE" in result["details"]["backend"]["tail"]

    def test_build_failure_marks_backend_build(self, tmp_path: Path):
        ws = _make_workspace(tmp_path)
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd[:3])
            if cmd[1] == "install":
                return _ok()
            return _fail(stdout="tsc error TS2304: cannot find name 'Foo'")

        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("subprocess.run", side_effect=fake_run):
            result = _verify_npm_build(str(ws))

        assert result["ok"] is False
        assert result["first_failure"] == "backend.build"
        assert result["details"]["backend"]["install"] == 0
        assert result["details"]["backend"]["build"] == 1
        assert "TS2304" in result["details"]["backend"]["tail"]

    def test_both_subdirs_pass(self, tmp_path: Path):
        ws = _make_workspace(tmp_path, with_backend=True, with_frontend=True)
        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("subprocess.run", return_value=_ok()):
            result = _verify_npm_build(str(ws))
        assert result["ok"] is True
        assert result["first_failure"] is None
        assert result["details"]["backend"]["install"] == 0
        assert result["details"]["backend"]["build"] == 0
        assert result["details"]["frontend"]["install"] == 0
        assert result["details"]["frontend"]["build"] == 0

    def test_no_build_script_with_tsconfig_runs_tsc(self, tmp_path: Path):
        # No "build" in scripts but tsconfig present -> falls back to npx tsc --noEmit.
        ws = _make_workspace(
            tmp_path,
            backend_pkg={"name": "b", "scripts": {"start": "node ."}},
            backend_tsconfig=True,
        )
        cmds: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            cmds.append(list(cmd))
            return _ok()

        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("subprocess.run", side_effect=fake_run):
            result = _verify_npm_build(str(ws))

        assert result["ok"] is True
        # Second call (after install) must be tsc --noEmit, not npm run build.
        tsc_call = cmds[1]
        assert tsc_call[-2:] == ["tsc", "--noEmit"]

    def test_no_build_script_no_tsconfig_install_only(self, tmp_path: Path):
        # No "build" in scripts and no tsconfig -> install pass alone counts as ok.
        ws = _make_workspace(
            tmp_path,
            backend_pkg={"name": "b", "scripts": {"start": "node ."}},
        )
        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("subprocess.run", return_value=_ok()) as mock_run:
            result = _verify_npm_build(str(ws))

        assert result["ok"] is True
        assert result["details"]["backend"]["build"] == 0
        assert result["details"]["backend"]["skipped"] == "no_build_script_no_tsconfig"
        # Only `install` should have been invoked (no second call).
        assert mock_run.call_count == 1

    def test_install_timeout_marks_failure(self, tmp_path: Path):
        ws = _make_workspace(tmp_path)
        timeout_err = subprocess.TimeoutExpired(cmd=["npm", "install"], timeout=600)

        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("subprocess.run", side_effect=timeout_err):
            result = _verify_npm_build(str(ws), timeout=600)

        assert result["ok"] is False
        assert result["first_failure"] == "backend.install"
        assert "timeout" in result["details"]["backend"]["tail"]

    def test_corrupt_package_json_marks_parse_failure(self, tmp_path: Path):
        ws = tmp_path / "draft_x"
        backend = ws / "backend"
        backend.mkdir(parents=True)
        (backend / "package.json").write_text("{ this is not json")

        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"):
            result = _verify_npm_build(str(ws))

        assert result["ok"] is False
        assert result["first_failure"] == "backend.parse"
        assert result["details"]["backend"]["skipped"].startswith("package_json_parse_error")

    def test_first_failure_records_first_subdir_only(self, tmp_path: Path):
        # Both backend and frontend fail install. first_failure must be backend
        # (deterministic order), not whichever subdir was processed last.
        ws = _make_workspace(tmp_path, with_backend=True, with_frontend=True)

        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("subprocess.run", return_value=_fail(stderr="boom")):
            result = _verify_npm_build(str(ws))

        assert result["ok"] is False
        assert result["first_failure"] == "backend.install"
        # Frontend should still be probed and recorded as failed too.
        assert result["details"]["frontend"]["install"] == 1
