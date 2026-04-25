"""File/shell tools for CrewAI agents, sandboxed to a per-draft workspace.

All paths are constrained to ``~/Sentinel/<draft_id>/``. Shell
commands are whitelisted to the small set needed for Next.js + backend builds.

Tools are meant to be attached to Build and Deploy crew agents so they can
materialize generated code to disk, run ``npm`` / ``prisma`` / ``flyctl`` and
curl endpoints without arbitrary filesystem or exec power.
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

log = logging.getLogger("sentinel_v2.tools.file")

WORKSPACES_ROOT = Path(os.environ.get("SENTINEL_WORKSPACES_ROOT", os.path.expanduser("~/Sentinel")))

# Commands an agent may invoke. Anything else is refused. Keep this list tight.
_SHELL_WHITELIST = {
    "npm",
    "npx",
    "pnpm",
    "node",
    "git",
    "prisma",
    "flyctl",
    "osv-scanner",
    "curl",
    "ls",
    "cat",
    "mkdir",
    "rm",
    "mv",
    "cp",
    "sh",
    "bash",
    "echo",
    "test",
}


def _resolve_workspace(workspace_dir: str) -> Path:
    """Resolve a workspace path and fail hard if it escapes ``WORKSPACES_ROOT``."""
    root = WORKSPACES_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    ws = Path(workspace_dir).resolve()
    if not str(ws).startswith(str(root)):
        raise ValueError(
            f"workspace_dir {workspace_dir!r} escapes {root}"
        )
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _safe_child(workspace: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` inside ``workspace`` or raise."""
    if ".." in Path(rel_path).parts:
        raise ValueError(f"path traversal attempt: {rel_path!r}")
    candidate = (workspace / rel_path).resolve()
    if not str(candidate).startswith(str(workspace)):
        raise ValueError(f"path {rel_path!r} escapes workspace {workspace}")
    return candidate


# ── WriteFileTool ─────────────────────────────────────────────────────────────


class WriteFileInput(BaseModel):
    workspace_dir: str = Field(..., description="Absolute workspace path, e.g. /tmp/sentinel_workspaces/draft_c0_foo")
    path: str = Field(..., description="Path relative to workspace_dir, e.g. 'backend/src/index.ts'")
    content: str = Field(..., description="Full file contents to write (overwrites existing)")


class WriteFileTool(BaseTool):
    name: str = "write_file"
    description: str = (
        "Write a file to the draft's workspace. Creates parent directories as needed. "
        "Path must be relative to workspace_dir and not escape the workspace."
    )
    args_schema: Type[BaseModel] = WriteFileInput

    def _run(self, workspace_dir: str, path: str, content: str) -> str:
        ws = _resolve_workspace(workspace_dir)
        dest = _safe_child(ws, path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        return f"wrote {dest.relative_to(ws)} ({len(content)} bytes)"


# ── ListFilesTool ─────────────────────────────────────────────────────────────


class ListFilesInput(BaseModel):
    workspace_dir: str = Field(..., description="Absolute workspace path")
    sub_path: str = Field(default=".", description="Subdirectory relative to workspace_dir")


class ListFilesTool(BaseTool):
    name: str = "list_files"
    description: str = "List files in the draft's workspace (optionally scoped to a subdirectory)."
    args_schema: Type[BaseModel] = ListFilesInput

    def _run(self, workspace_dir: str, sub_path: str = ".") -> str:
        ws = _resolve_workspace(workspace_dir)
        base = _safe_child(ws, sub_path)
        if not base.exists():
            return "(empty)"
        items: list[str] = []
        for p in sorted(base.rglob("*")):
            if "node_modules" in p.parts or ".git" in p.parts or ".next" in p.parts:
                continue
            rel = p.relative_to(ws)
            kind = "d" if p.is_dir() else "f"
            items.append(f"{kind} {rel}")
        return "\n".join(items) if items else "(empty)"


# ── RunShellTool ──────────────────────────────────────────────────────────────


class RunShellInput(BaseModel):
    workspace_dir: str = Field(..., description="Absolute workspace path (cwd for the command)")
    command: str = Field(..., description="Shell command, first token must be whitelisted")
    timeout_seconds: int = Field(default=300, description="Max runtime (1-1800)")


class RunShellTool(BaseTool):
    name: str = "run_shell"
    description: str = (
        "Run a shell command inside the workspace. First token must be one of: "
        + ", ".join(sorted(_SHELL_WHITELIST))
        + ". Returns combined stdout/stderr (truncated to 4000 chars) and exit code."
    )
    args_schema: Type[BaseModel] = RunShellInput

    def _run(self, workspace_dir: str, command: str, timeout_seconds: int = 300) -> str:
        ws = _resolve_workspace(workspace_dir)
        try:
            argv = shlex.split(command)
        except ValueError as e:
            return f"shell-parse-error: {e}"
        if not argv:
            return "shell-error: empty command"
        binary = os.path.basename(argv[0])
        if binary not in _SHELL_WHITELIST:
            return f"shell-error: {binary!r} not in whitelist"

        timeout = max(1, min(int(timeout_seconds), 1800))
        try:
            proc = subprocess.run(
                argv,
                cwd=str(ws),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"shell-timeout: exceeded {timeout}s"
        except FileNotFoundError:
            return f"shell-error: binary {binary!r} not found in PATH"

        out = (proc.stdout or "") + (proc.stderr or "")
        if len(out) > 4000:
            out = out[:4000] + f"\n…(truncated, total={len(out)} chars)"
        return f"exit={proc.returncode}\n{out}"
