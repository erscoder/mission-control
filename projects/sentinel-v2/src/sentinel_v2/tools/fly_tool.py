"""fly.io tools for CrewAI agents.

Thin wrappers around the ``flyctl`` CLI (requires the binary to be on PATH).
All commands are scoped to a single Fly organization (defaults to ``personal``)
and authenticate via ``FLY_API_TOKEN`` passed in the environment.

The CLI is preferred over raw GraphQL because ``flyctl deploy`` handles the
Dockerfile build, volume attachments, health checks, and rollback plumbing for
free — wrapping it in Python would duplicate hundreds of lines of logic.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

log = logging.getLogger("sentinel_v2.tools.fly")

_APP_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")


def _fly_env() -> dict[str, str]:
    token = os.environ.get("FLY_API_TOKEN")
    if not token:
        raise RuntimeError("FLY_API_TOKEN not set")
    env = os.environ.copy()
    env["FLY_API_TOKEN"] = token
    return env


def _run_flyctl(args: list[str], timeout: int = 600, cwd: str | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["flyctl", *args],
            env=_fly_env(),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "flyctl binary not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, f"flyctl timed out after {timeout}s"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


# ── FlyAppCreateTool ─────────────────────────────────────────────────────────


class FlyAppCreateInput(BaseModel):
    app_name: str = Field(..., description="Globally unique lowercase slug (1-30 chars, a-z0-9-)")
    org: str = Field(default="personal", description="Fly organization slug")
    region: str = Field(default="iad", description="Primary region, e.g. iad, fra, cdg")


class FlyAppCreateTool(BaseTool):
    name: str = "fly_app_create"
    description: str = (
        "Create a Fly.io app with the given name. Idempotent: if the app already "
        "exists (and is owned by the org), returns its info. Returns {app_name, app_url}."
    )
    args_schema: Type[BaseModel] = FlyAppCreateInput

    def _run(self, app_name: str, org: str = "personal", region: str = "iad") -> str:
        if not _APP_NAME_RE.match(app_name):
            return f"error: app_name {app_name!r} invalid (must match {_APP_NAME_RE.pattern})"

        # Check existence
        rc, out = _run_flyctl(["apps", "list", "--json"])
        if rc == 0:
            try:
                apps = json.loads(out)
                if any(a.get("Name") == app_name for a in apps):
                    return json.dumps({
                        "app_name": app_name,
                        "app_url": f"https://{app_name}.fly.dev",
                        "reused": True,
                    })
            except json.JSONDecodeError:
                pass

        rc, out = _run_flyctl([
            "apps", "create", app_name,
            "--org", org,
        ])
        if rc != 0 and "taken" not in out.lower():
            return f"error rc={rc}: {out[:1000]}"

        return json.dumps({
            "app_name": app_name,
            "app_url": f"https://{app_name}.fly.dev",
            "region": region,
            "reused": False,
        })


# ── FlySecretsSetTool ────────────────────────────────────────────────────────


class FlySecretsSetInput(BaseModel):
    app_name: str = Field(..., description="Target Fly app")
    secrets: dict[str, str] = Field(..., description="Env vars to set on the app")
    stage: bool = Field(default=False, description="If true, stage without deploying a new release")


class FlySecretsSetTool(BaseTool):
    name: str = "fly_secrets_set"
    description: str = (
        "Set one or more secret env vars on a Fly app. By default triggers a new release; "
        "pass stage=true to accumulate secrets for the next deploy."
    )
    args_schema: Type[BaseModel] = FlySecretsSetInput

    def _run(self, app_name: str, secrets: dict[str, str], stage: bool = False) -> str:
        if not secrets:
            return json.dumps({"set": []})
        args = ["secrets", "set", "--app", app_name]
        if stage:
            args.append("--stage")
        args.extend([f"{k}={shlex.quote(v)}" for k, v in secrets.items()])
        rc, out = _run_flyctl(args, timeout=120)
        if rc != 0:
            return f"error rc={rc}: {out[:1000]}"
        return json.dumps({"set": list(secrets.keys()), "staged": stage})


# ── FlyDeployTool ────────────────────────────────────────────────────────────


class FlyDeployInput(BaseModel):
    app_name: str = Field(..., description="Target Fly app")
    source_dir: str = Field(..., description="Directory containing Dockerfile + fly.toml")
    dockerfile: str | None = Field(default=None, description="Optional Dockerfile path relative to source_dir")


class FlyDeployTool(BaseTool):
    name: str = "fly_deploy"
    description: str = (
        "Build and deploy an app to Fly.io via `flyctl deploy`. Requires a Dockerfile "
        "and fly.toml in source_dir (the agent should write them via WriteFileTool). "
        "Returns {app_name, url, version}."
    )
    args_schema: Type[BaseModel] = FlyDeployInput

    def _run(self, app_name: str, source_dir: str, dockerfile: str | None = None) -> str:
        args = ["deploy", "--app", app_name, "--remote-only"]
        if dockerfile:
            args.extend(["--dockerfile", dockerfile])
        rc, out = _run_flyctl(args, timeout=1800, cwd=source_dir)
        if rc != 0:
            return f"error rc={rc}: {out[-2000:]}"
        # Extract version from output if present
        version = None
        for line in out.splitlines():
            m = re.search(r"release\s+v(\d+)", line, re.IGNORECASE)
            if m:
                version = int(m.group(1))
                break
        return json.dumps({
            "app_name": app_name,
            "url": f"https://{app_name}.fly.dev",
            "version": version,
        })


# ── FlyStatusTool ────────────────────────────────────────────────────────────


class FlyStatusInput(BaseModel):
    app_name: str = Field(..., description="Target Fly app")


class FlyStatusTool(BaseTool):
    name: str = "fly_status"
    description: str = "Return health and running machines for a Fly app."
    args_schema: Type[BaseModel] = FlyStatusInput

    def _run(self, app_name: str) -> str:
        rc, out = _run_flyctl(["status", "--app", app_name, "--json"], timeout=60)
        if rc != 0:
            return f"error rc={rc}: {out[:1000]}"
        try:
            return json.dumps(json.loads(out))
        except json.JSONDecodeError:
            return out[:2000]
