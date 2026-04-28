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
import re
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
    # Build / package managers
    "npm", "npx", "pnpm", "node", "yarn",
    # VCS
    "git",
    # ORMs / deploy CLIs
    "prisma", "flyctl",
    # Security scanners
    "osv-scanner",
    # HTTP
    "curl",
    # Filesystem read-only inspection
    "ls", "cat", "head", "tail", "find", "grep", "wc", "pwd", "which", "stat",
    # Filesystem write (workspace-scoped via cwd)
    "mkdir", "rm", "mv", "cp", "touch", "chmod",
    # Shell + misc
    "sh", "bash", "echo", "test", "true", "false",
}

# Pattern: ``cd <subdir> && <rest>``. Agents fall back to this when they want
# to run a command in a sub-directory of the workspace; subprocess.run does
# not invoke a shell, so the literal `cd` would fail. We extract the subdir
# and the rest of the command transparently.
_CD_PREFIX = re.compile(r"^\s*cd\s+([^\s&;]+)\s*&&\s*(.+)$", re.DOTALL)


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
    workspace_dir: str = Field(..., description="Absolute workspace path")
    command: str = Field(
        ...,
        description=(
            "Shell command. First token must be whitelisted. The 'cd <subdir> && <rest>' "
            "pattern is supported and translated to subdir + rest automatically."
        ),
    )
    subdir: str = Field(
        default=".",
        description=(
            "Optional sub-directory of workspace_dir to run the command in "
            "(e.g. 'frontend', 'backend'). Defaults to the workspace root."
        ),
    )
    timeout_seconds: int = Field(default=300, description="Max runtime (1-1800)")


class RunShellTool(BaseTool):
    name: str = "run_shell"
    description: str = (
        "Run a shell command inside the workspace (or a sub-directory via the "
        "'subdir' parameter). The 'cd <path> && <cmd>' pattern is also accepted "
        "and translated to subdir+cmd transparently. First token of the actual "
        "command must be one of: "
        + ", ".join(sorted(_SHELL_WHITELIST))
        + ". Returns combined stdout/stderr (truncated to 4000 chars) and exit code."
    )
    args_schema: Type[BaseModel] = RunShellInput

    def _run(
        self,
        workspace_dir: str,
        command: str,
        subdir: str = ".",
        timeout_seconds: int = 300,
    ) -> str:
        ws = _resolve_workspace(workspace_dir)

        # Translate 'cd <subdir> && <rest>' into the structured form.
        m = _CD_PREFIX.match(command)
        if m:
            translated_subdir, command = m.group(1), m.group(2)
            if subdir == "." or subdir == "":
                subdir = translated_subdir
            else:
                # Both explicit subdir AND inline cd; combine them.
                subdir = str(Path(subdir) / translated_subdir)

        # Resolve cwd safely
        try:
            cwd = _safe_child(ws, subdir) if subdir not in (".", "") else ws
        except ValueError as e:
            return f"shell-error: {e}"
        if not cwd.is_dir():
            return f"shell-error: subdir {subdir!r} does not exist under workspace"

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
                cwd=str(cwd),
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
