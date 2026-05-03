"""Tests for osv_scanner_tool.py - summary parsing + subprocess mocking."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentinel_v2.tools.osv_scanner_tool import OsvScannerTool, _summarize


def _mock_proc(rc: int, stdout: str = "", stderr: str = ""):
    return MagicMock(returncode=rc, stdout=stdout, stderr=stderr)


@pytest.fixture
def workspaces_root(tmp_path, monkeypatch):
    """Override the module-level WORKSPACES_ROOT so the new scan_dir guard
    accepts tmp_path-based scan targets. Without this every _run test would
    short-circuit with 'escapes workspaces root'.
    """
    monkeypatch.setattr(
        "sentinel_v2.tools.osv_scanner_tool.WORKSPACES_ROOT", tmp_path
    )
    return tmp_path


# ── _summarize ───────────────────────────────────────────────────────────────


def test_summarize_empty_report():
    summary = _summarize({"results": []})
    assert summary["total"] == 0
    assert summary["counts"]["CRITICAL"] == 0
    assert summary["findings"] == []


def test_summarize_single_critical_finding():
    report = {
        "results": [{
            "packages": [{
                "package": {"name": "lodash", "version": "4.17.4", "ecosystem": "npm"},
                "vulnerabilities": [{
                    "id": "GHSA-xxxx",
                    "summary": "Prototype pollution",
                    "aliases": ["CVE-2019-10744"],
                    "database_specific": {"severity": "CRITICAL"},
                    "affected": [{
                        "ranges": [{
                            "events": [{"introduced": "0"}, {"fixed": "4.17.12"}],
                        }],
                    }],
                }],
            }],
        }],
    }
    summary = _summarize(report)
    assert summary["total"] == 1
    assert summary["counts"]["CRITICAL"] == 1
    assert len(summary["findings"]) == 1
    f = summary["findings"][0]
    assert f["package"] == "lodash"
    assert f["installed"] == "4.17.4"
    assert f["severity"] == "CRITICAL"
    assert f["fix_versions"] == ["4.17.12"]
    assert "CVE-2019-10744" in f["aliases"]


def test_summarize_no_fix_version():
    report = {
        "results": [{
            "packages": [{
                "package": {"name": "abandoned", "version": "1.0.0", "ecosystem": "npm"},
                "vulnerabilities": [{
                    "id": "GHSA-zzzz",
                    "summary": "Unpatched",
                    "database_specific": {"severity": "HIGH"},
                    "affected": [{"ranges": [{"events": [{"introduced": "0"}]}]}],
                }],
            }],
        }],
    }
    summary = _summarize(report)
    assert summary["findings"][0]["fix_versions"] == []
    assert summary["findings"][0]["severity"] == "HIGH"


def test_summarize_moderate_maps_to_medium():
    report = {
        "results": [{
            "packages": [{
                "package": {"name": "foo", "version": "1.0", "ecosystem": "npm"},
                "vulnerabilities": [{
                    "id": "GHSA-aaaa",
                    "database_specific": {"severity": "MODERATE"},
                }],
            }],
        }],
    }
    summary = _summarize(report)
    assert summary["counts"]["MEDIUM"] == 1
    assert summary["findings"][0]["severity"] == "MEDIUM"


def test_summarize_sorts_by_severity_desc():
    report = {
        "results": [{
            "packages": [
                {
                    "package": {"name": "low", "version": "1.0", "ecosystem": "npm"},
                    "vulnerabilities": [{
                        "id": "A", "database_specific": {"severity": "LOW"},
                    }],
                },
                {
                    "package": {"name": "crit", "version": "1.0", "ecosystem": "npm"},
                    "vulnerabilities": [{
                        "id": "B", "database_specific": {"severity": "CRITICAL"},
                    }],
                },
                {
                    "package": {"name": "high", "version": "1.0", "ecosystem": "npm"},
                    "vulnerabilities": [{
                        "id": "C", "database_specific": {"severity": "HIGH"},
                    }],
                },
            ],
        }],
    }
    summary = _summarize(report)
    sevs = [f["severity"] for f in summary["findings"]]
    assert sevs == ["CRITICAL", "HIGH", "LOW"]


# ── OsvScannerTool._run ──────────────────────────────────────────────────────


def test_run_reports_missing_binary(workspaces_root):
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value=None):
        result = OsvScannerTool()._run(scan_dir=str(workspaces_root))
    data = json.loads(result)
    assert "error" in data
    assert "osv-scanner" in data["error"]


def test_run_rejects_nonexistent_dir(workspaces_root):
    # Subdir of workspaces_root that does not exist - passes the new sandbox
    # guard but fails the existence check.
    target = workspaces_root / "missing"
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"):
        result = OsvScannerTool()._run(scan_dir=str(target))
    data = json.loads(result)
    assert "error" in data
    assert "not a directory" in data["error"]


def test_run_parses_clean_scan(workspaces_root):
    clean_json = json.dumps({"results": []})
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(0, clean_json),
         ):
        result = OsvScannerTool()._run(scan_dir=str(workspaces_root))
    data = json.loads(result)
    assert data["total"] == 0
    assert data["scan_dir"] == str(workspaces_root)


def test_run_parses_vulns_found(workspaces_root):
    vulns_json = json.dumps({
        "results": [{
            "packages": [{
                "package": {"name": "lodash", "version": "4.17.4", "ecosystem": "npm"},
                "vulnerabilities": [{
                    "id": "GHSA-x",
                    "database_specific": {"severity": "HIGH"},
                    "affected": [{"ranges": [{"events": [{"fixed": "4.17.12"}]}]}],
                }],
            }],
        }],
    })
    # rc=1 is normal when osv-scanner finds vulns
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(1, vulns_json),
         ):
        result = OsvScannerTool()._run(scan_dir=str(workspaces_root))
    data = json.loads(result)
    assert data["total"] == 1
    assert data["counts"]["HIGH"] == 1
    assert data["findings"][0]["package"] == "lodash"


def test_run_handles_non_json_output(workspaces_root):
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(0, "not json"),
         ):
        result = OsvScannerTool()._run(scan_dir=str(workspaces_root))
    data = json.loads(result)
    assert "error" in data
    assert "not JSON" in data["error"]


def test_run_handles_timeout(workspaces_root):
    import subprocess as _sp
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             side_effect=_sp.TimeoutExpired(cmd="osv-scanner", timeout=600),
         ):
        result = OsvScannerTool()._run(scan_dir=str(workspaces_root))
    data = json.loads(result)
    assert "error" in data
    assert "timed out" in data["error"]


def test_run_handles_bad_rc(workspaces_root):
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(127, "", "internal error"),
         ):
        result = OsvScannerTool()._run(scan_dir=str(workspaces_root))
    data = json.loads(result)
    assert "error" in data
    assert "rc=127" in data["error"]


# ── New: scan_dir sandbox guard (defense-in-depth) ───────────────────────────


def test_run_rejects_scan_dir_outside_workspaces_root(workspaces_root):
    """Agents calling osv_scan('/etc') wander host info-disclosure paths even
    inside a container; the new guard short-circuits before subprocess.run.
    """
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"):
        result = OsvScannerTool()._run(scan_dir="/etc")
    data = json.loads(result)
    assert "error" in data
    assert "escapes workspaces root" in data["error"]


def test_run_rejects_scan_dir_traversal(workspaces_root):
    """`../foo` inside workspaces_root that resolves OUTSIDE the root must be
    rejected - belt-and-suspenders against agents trying to climb out.
    """
    target = workspaces_root / ".." / "definitely_outside"
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"):
        result = OsvScannerTool()._run(scan_dir=str(target))
    data = json.loads(result)
    assert "error" in data
    assert "escapes workspaces root" in data["error"]


def test_run_accepts_workspaces_root_itself(workspaces_root):
    """The root directory itself is a valid scan target (scans every draft)."""
    clean_json = json.dumps({"results": []})
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(0, clean_json),
         ):
        result = OsvScannerTool()._run(scan_dir=str(workspaces_root))
    data = json.loads(result)
    assert "error" not in data
    assert data["total"] == 0


def test_run_accepts_subpath_of_workspaces_root(workspaces_root):
    """Per-draft scan targets like <root>/draft_c1_foo/backend stay allowed."""
    sub = workspaces_root / "draft_c1_foo" / "backend"
    sub.mkdir(parents=True)
    clean_json = json.dumps({"results": []})
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(0, clean_json),
         ):
        result = OsvScannerTool()._run(scan_dir=str(sub))
    data = json.loads(result)
    assert data["total"] == 0
    assert data["scan_dir"] == str(sub)
