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
# `sh` and `bash` are deliberately omitted: `sh -c "<arbitrary>"` re-introduces
# unrestricted shell expansion (pipes, redirects, command substitution) that
# bypasses the per-binary path validation below. Agents that need a shell
# pipeline must split it into separate run_shell calls.
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
    # Misc
    "echo", "test", "true", "false",
}

# Binaries that mutate the filesystem. Every non-flag positional argument
# passed to one of these MUST resolve to a path inside the workspace — agents
# have, on a hallucinated "manual cleanup" path, attempted `rm -rf ~` and
# `mv ../* /tmp`. The validator below rejects anything that escapes the
# workspace via absolute paths, `..` traversal, or `~` expansion.
_PATH_MUTATING_BINARIES = {"rm", "mv", "cp", "chmod", "touch", "mkdir"}

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


def _validate_destructive_argv(
    binary: str, argv: list[str], cwd: Path, workspace: Path
) -> str | None:
    """For path-mutating binaries, every non-flag positional argument MUST
    resolve to a path inside ``workspace``. Returns an error string when a
    path escapes (absolute path outside workspace, ``..`` traversal up past
    workspace, ``~`` expansion to the operator's home, etc.) or ``None`` when
    the argv is safe to execute.

    This is an in-process defense-in-depth layer: even though run_shell uses
    ``cwd=workspace`` and ``shell=False``, ``rm -rf /Users/kike/Documents``
    will still execute happily because the absolute path is interpreted by
    ``rm``, not by the shell. Block such argv before subprocess.run sees it.
    """
    if binary not in _PATH_MUTATING_BINARIES:
        return None
    for tok in argv[1:]:
        # Flag tokens (single ``-`` or long ``--name``). Catches ``-rf``,
        # ``--recursive``, ``--``, etc. The bare ``-`` is treated as flag too.
        if tok.startswith("-"):
            continue
        # Empty tokens (rare; shlex.split keeps them only on quoted "" args)
        if not tok:
            continue
        # ``~`` expansion is a Python-level concern: shlex.split keeps the
        # literal ``~``, but Path.expanduser() would resolve to the operator
        # home. Treat any leading ``~`` as an immediate escape attempt.
        if tok.startswith("~"):
            return (
                f"shell-error: destructive binary {binary!r} cannot operate on "
                f"path {tok!r} (~ expands to operator home, outside workspace)"
            )
        try:
            candidate = Path(tok)
            target = (candidate if candidate.is_absolute() else (cwd / candidate)).resolve()
        except Exception as e:
            return f"shell-error: cannot resolve path {tok!r} for {binary!r}: {e}"
        if not str(target).startswith(str(workspace)):
            return (
                f"shell-error: destructive binary {binary!r} cannot operate on "
                f"{tok!r} (resolves to {target}, outside workspace {workspace})"
            )
    return None


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
            "Shell command. First token must be whitelisted. ONE COMMAND PER CALL — "
            "shell operators &&, ||, ;, and | are rejected. Make separate run_shell "
            "calls per command. The 'cd <subdir> && <rest>' pattern is the only "
            "exception and is translated to subdir + rest automatically."
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
        "Run ONE shell command inside the workspace (or a sub-directory via the "
        "'subdir' parameter). Do NOT chain commands: '&&', '||', ';', '|' are "
        "rejected — issue a separate run_shell call per command. The 'cd <path> "
        "&& <cmd>' prefix is the only allowed chain and is translated to "
        "subdir+cmd transparently. First token of the actual command must be "
        "one of: "
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

        # Reject shell operators surfaced as bare tokens after shlex.split.
        # subprocess.run with shell=False would silently pass them as
        # arguments (e.g. 'npm install foo && npm install bar' becomes a
        # tag name '&&' to npm, causing EINVALIDTAGNAME). Force agents to
        # make separate calls per command.
        #
        # Includes shell redirects (`2>&1`, `>`, `>>`, `<`, `<<`, `&>`):
        # observed live, the build agent ran `npx tsc 2>&1` and tsc treated
        # `2>&1` as a path argument because shlex preserves it as a single
        # token; tsc then fails with TS6231 'Could not resolve the path 2>&1'
        # forever, agent reads the unhelpful error, retries the same shell
        # form, build attempt exhausts on a non-issue. Reject early with a
        # clear error so the agent can correct.
        _SHELL_OPS = {
            "&&", "||", ";", "|",
            ">", ">>", "<", "<<",
            "2>&1", "2>", "1>", "&>", "1>&2", "2>&-",
        }
        for tok in argv:
            if tok in _SHELL_OPS:
                return (
                    f"shell-error: shell operator {tok!r} not supported. "
                    "subprocess.run uses shell=False so redirects and pipes "
                    "do not work. Issue one run_shell call per command and "
                    "read the captured output from the tool result. The only "
                    "allowed chain is a leading 'cd <subdir> && <cmd>'."
                )

        binary = os.path.basename(argv[0])
        if binary not in _SHELL_WHITELIST:
            return f"shell-error: {binary!r} not in whitelist"

        # Defense-in-depth: subprocess.run's cwd parameter only sets where the
        # process starts; absolute paths in argv (e.g. `rm -rf /Users/kike/...`)
        # bypass that constraint completely. Validate every path-touching
        # argument for path-mutating binaries before letting subprocess see it.
        argv_err = _validate_destructive_argv(binary, argv, cwd, ws)
        if argv_err:
            return argv_err

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
