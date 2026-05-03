"""Tests for file_tool.py — workspace sandboxing and shell whitelist."""
from __future__ import annotations

import pytest
from pathlib import Path

from sentinel_v2.tools.file_tool import (
    ListFilesTool,
    RunShellTool,
    WriteFileTool,
    _resolve_workspace,
    _safe_child,
)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Isolated workspaces root under pytest's tmp_path."""
    root = tmp_path / "workspaces"
    monkeypatch.setenv("SENTINEL_WORKSPACES_ROOT", str(root))
    # Patch module-level constant — it reads env only at import
    from sentinel_v2.tools import file_tool as ft
    monkeypatch.setattr(ft, "WORKSPACES_ROOT", root)
    ws = root / "draft_c0_test"
    ws.mkdir(parents=True)
    return ws


# ── _resolve_workspace ────────────────────────────────────────────────────────


def test_resolve_workspace_accepts_valid_path(workspace):
    resolved = _resolve_workspace(str(workspace))
    assert resolved == workspace.resolve()


def test_resolve_workspace_rejects_escape(workspace, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        _resolve_workspace(str(outside))


# ── _safe_child ──────────────────────────────────────────────────────────────


def test_safe_child_accepts_nested_path(workspace):
    path = _safe_child(workspace, "backend/src/index.ts")
    assert str(path).startswith(str(workspace))


def test_safe_child_rejects_dotdot(workspace):
    with pytest.raises(ValueError, match="traversal"):
        _safe_child(workspace, "../outside.ts")


def test_safe_child_rejects_absolute_outside(workspace):
    # Absolute path that resolves outside workspace
    with pytest.raises(ValueError, match="escapes"):
        _safe_child(workspace, "/etc/passwd")


# ── WriteFileTool ────────────────────────────────────────────────────────────


def test_write_file_creates_file(workspace):
    tool = WriteFileTool()
    result = tool._run(
        workspace_dir=str(workspace),
        path="backend/index.ts",
        content="console.log('hi')",
    )
    assert "wrote" in result
    assert (workspace / "backend" / "index.ts").read_text() == "console.log('hi')"


def test_write_file_refuses_traversal(workspace):
    tool = WriteFileTool()
    with pytest.raises(ValueError):
        tool._run(workspace_dir=str(workspace), path="../evil.ts", content="x")


# ── ListFilesTool ────────────────────────────────────────────────────────────


def test_list_files_empty_workspace(workspace):
    tool = ListFilesTool()
    assert tool._run(workspace_dir=str(workspace)) == "(empty)"


def test_list_files_after_write(workspace):
    WriteFileTool()._run(
        workspace_dir=str(workspace), path="a.ts", content="x"
    )
    WriteFileTool()._run(
        workspace_dir=str(workspace), path="dir/b.ts", content="y"
    )
    listing = ListFilesTool()._run(workspace_dir=str(workspace))
    assert "a.ts" in listing
    assert "dir/b.ts" in listing


def test_list_files_skips_node_modules(workspace):
    (workspace / "node_modules" / "foo").mkdir(parents=True)
    (workspace / "node_modules" / "foo" / "pkg.js").write_text("x")
    listing = ListFilesTool()._run(workspace_dir=str(workspace))
    assert "node_modules" not in listing


# ── RunShellTool ─────────────────────────────────────────────────────────────


def test_run_shell_rejects_non_whitelist(workspace):
    tool = RunShellTool()
    result = tool._run(workspace_dir=str(workspace), command="curlish http://evil")
    assert "not in whitelist" in result


def test_run_shell_rejects_rm_rf_outside(workspace):
    """Whitelist includes rm but cwd is workspace — escape via absolute path still limited."""
    tool = RunShellTool()
    # This shouldn't be blocked by whitelist (rm is allowed), but the cwd is the workspace
    # so any damage is contained to the workspace dir.
    result = tool._run(workspace_dir=str(workspace), command="rm -rf .")
    # It runs (exit=0 or exit≠0) but only deletes workspace contents
    assert result.startswith("exit=")


def test_run_shell_empty_command(workspace):
    tool = RunShellTool()
    result = tool._run(workspace_dir=str(workspace), command="")
    assert "shell-error" in result


def test_run_shell_echo_works(workspace):
    tool = RunShellTool()
    result = tool._run(workspace_dir=str(workspace), command="echo hello")
    assert "exit=0" in result
    assert "hello" in result


def test_run_shell_rejects_double_ampersand(workspace):
    """Shell chains via && must be rejected.

    Regression for the npm `EINVALIDTAGNAME "&&"` daemon failures: agents
    were calling `run_shell('npm install foo && npm install bar')` which
    `shlex.split` turned into `['npm', 'install', 'foo', '&&', 'npm', ...]`.
    npm then read `&&` as a tag name and crashed every install.
    """
    tool = RunShellTool()
    result = tool._run(
        workspace_dir=str(workspace),
        command="echo a && echo b",
    )
    assert "shell-error" in result
    assert "&&" in result


def test_run_shell_rejects_semicolon(workspace):
    tool = RunShellTool()
    result = tool._run(workspace_dir=str(workspace), command="echo a ; echo b")
    assert "shell-error" in result
    assert ";" in result


def test_run_shell_rejects_pipe(workspace):
    tool = RunShellTool()
    result = tool._run(workspace_dir=str(workspace), command="echo a | echo b")
    assert "shell-error" in result
    assert "|" in result


def test_run_shell_allows_leading_cd_chain(workspace):
    """The 'cd <subdir> && <cmd>' prefix is the one allowed chain."""
    (workspace / "frontend").mkdir()
    tool = RunShellTool()
    result = tool._run(
        workspace_dir=str(workspace),
        command="cd frontend && echo here",
    )
    assert "exit=0" in result
    assert "here" in result


# ── Argv path-validation: defense-in-depth against `rm -rf` outside ws ───────


def test_run_shell_rejects_rm_absolute_outside_workspace(workspace):
    """rm with an absolute path outside the workspace must be refused."""
    tool = RunShellTool()
    result = tool._run(
        workspace_dir=str(workspace),
        command="rm -rf /tmp/some-other-dir",
    )
    assert "shell-error" in result
    assert "outside workspace" in result


def test_run_shell_rejects_mv_to_operator_home(workspace):
    """mv targeting ~ (operator home) must be refused."""
    tool = RunShellTool()
    result = tool._run(
        workspace_dir=str(workspace),
        command="mv dist ~/stash",
    )
    assert "shell-error" in result
    assert "~" in result


def test_run_shell_rejects_rm_traversal(workspace):
    """rm with `..` traversing past the workspace must be refused."""
    tool = RunShellTool()
    result = tool._run(
        workspace_dir=str(workspace),
        command="rm -rf ../../etc/passwd",
    )
    assert "shell-error" in result


def test_run_shell_allows_rm_inside_workspace(workspace):
    """rm of a path inside the workspace stays allowed (the agent's
    legitimate `rm -rf dist tsconfig.tsbuildinfo` cleanup case).
    """
    (workspace / "dist").mkdir()
    (workspace / "dist" / "stale.js").write_text("// old")
    tool = RunShellTool()
    result = tool._run(
        workspace_dir=str(workspace),
        command="rm -rf dist",
    )
    assert "exit=0" in result
    assert not (workspace / "dist").exists()


def test_run_shell_rejects_sh_after_whitelist_tightening(workspace):
    """sh is removed from the whitelist because `sh -c '...'` re-introduces
    full shell expansion that bypasses the per-binary path validation.
    """
    tool = RunShellTool()
    result = tool._run(
        workspace_dir=str(workspace),
        command="sh -c 'rm -rf /tmp/pwn'",
    )
    assert "shell-error" in result
    assert "not in whitelist" in result


def test_run_shell_rejects_bash_after_whitelist_tightening(workspace):
    tool = RunShellTool()
    result = tool._run(
        workspace_dir=str(workspace),
        command="bash -c 'rm -rf /tmp/pwn'",
    )
    assert "shell-error" in result
    assert "not in whitelist" in result
