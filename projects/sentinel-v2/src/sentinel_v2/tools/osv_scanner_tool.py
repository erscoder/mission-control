"""OSV-Scanner tool for CrewAI agents.

Wraps the ``osv-scanner`` binary (https://github.com/google/osv-scanner) to
detect known vulnerabilities in dependency manifests (``package-lock.json``,
``pnpm-lock.yaml``, ``yarn.lock``, ``Cargo.lock``, ``requirements.txt``, …)
across a workspace directory.

The binary must be on PATH inside the daemon container (installed via the
``Dockerfile``). The tool returns a structured JSON summary the remediation
planner can reason about.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from sentinel_v2.tools.file_tool import WORKSPACES_ROOT

log = logging.getLogger("sentinel_v2.tools.osv")


_SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


def _pick_severity(vuln: dict) -> str:
    """Return the highest severity across OSV + database_specific fields."""
    sevs: list[str] = []
    for s in vuln.get("severity", []) or []:
        sevs.append((s.get("type") or "").upper() if False else "")  # placeholder
    # database_specific.severity is the actionable label
    ds = vuln.get("database_specific") or {}
    if ds.get("severity"):
        sevs.append(str(ds["severity"]).upper())
    for aff in vuln.get("affected", []) or []:
        ads = (aff.get("database_specific") or {}).get("severity")
        if ads:
            sevs.append(str(ads).upper())
    if not sevs:
        return "UNKNOWN"
    return max(sevs, key=lambda s: _SEVERITY_ORDER.get(s, 0))


def _summarize(report_json: dict) -> dict[str, Any]:
    """Boil osv-scanner's verbose JSON down to what the planner needs."""
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
    findings: list[dict] = []
    results = report_json.get("results") or []
    for result_block in results:
        for pkg in result_block.get("packages") or []:
            info = pkg.get("package") or {}
            installed = info.get("version", "?")
            name = info.get("name", "?")
            ecosystem = info.get("ecosystem", "?")
            for vuln in pkg.get("vulnerabilities") or []:
                sev = _pick_severity(vuln)
                if sev == "MODERATE":
                    sev = "MEDIUM"
                counts[sev] = counts.get(sev, 0) + 1
                fix_versions: list[str] = []
                for aff in vuln.get("affected") or []:
                    for r in aff.get("ranges") or []:
                        for ev in r.get("events") or []:
                            if ev.get("fixed"):
                                fix_versions.append(ev["fixed"])
                findings.append({
                    "package": name,
                    "ecosystem": ecosystem,
                    "installed": installed,
                    "id": vuln.get("id"),
                    "severity": sev,
                    "summary": (vuln.get("summary") or "")[:200],
                    "fix_versions": sorted(set(fix_versions)),
                    "aliases": vuln.get("aliases") or [],
                })
    total = sum(counts.values())
    # Severity-sorted for planner convenience
    findings.sort(key=lambda f: (-_SEVERITY_ORDER.get(f["severity"], 0), f["package"]))
    return {
        "total": total,
        "counts": counts,
        "findings": findings,
    }


class OsvScanInput(BaseModel):
    scan_dir: str = Field(..., description="Absolute path to scan (e.g. <workspace>/backend or <workspace>/frontend). osv-scanner recurses.")


class OsvScannerTool(BaseTool):
    name: str = "osv_scan"
    description: str = (
        "Run osv-scanner against a directory and return a JSON summary: "
        "{total, counts: {CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN}, findings: [...]}. "
        "Each finding has package, ecosystem, installed, id (CVE/GHSA), severity, "
        "summary, and fix_versions (sorted list of versions that patch the issue, "
        "empty if none exists yet — planner must then downgrade)."
    )
    args_schema: Type[BaseModel] = OsvScanInput

    def _run(self, scan_dir: str) -> str:
        if not shutil.which("osv-scanner"):
            return json.dumps({"error": "osv-scanner binary not on PATH"})
        # Defense-in-depth: even with the daemon running inside a container
        # bind-mounted only at /root/Sentinel, an agent calling
        # osv_scan('/etc') still wanders info-disclosure paths. Reject any
        # scan_dir that is not the workspaces root or a subpath of it.
        try:
            root = WORKSPACES_ROOT.resolve()
            target = Path(scan_dir).resolve()
        except Exception as e:
            return json.dumps({"error": f"scan_dir resolve failed: {e}"})
        if target != root and not str(target).startswith(str(root) + os.sep):
            return json.dumps({"error": f"scan_dir {scan_dir!r} escapes workspaces root {root}"})
        if not os.path.isdir(scan_dir):
            return json.dumps({"error": f"scan_dir not a directory: {scan_dir}"})

        try:
            proc = subprocess.run(
                ["osv-scanner", "--format=json", "--recursive", scan_dir],
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "osv-scanner timed out after 600s"})
        except FileNotFoundError:
            return json.dumps({"error": "osv-scanner binary not found"})

        # Exit codes: 0 = clean, 1 = vulns found, 127 = error. stdout has JSON in both 0 and 1.
        raw = proc.stdout or proc.stderr or ""
        if proc.returncode not in (0, 1):
            return json.dumps({
                "error": f"osv-scanner rc={proc.returncode}",
                "output": raw[:2000],
            })

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps({
                "error": "osv-scanner output was not JSON",
                "output": raw[:2000],
            })

        summary = _summarize(data)
        summary["scan_dir"] = scan_dir
        return json.dumps(summary)
