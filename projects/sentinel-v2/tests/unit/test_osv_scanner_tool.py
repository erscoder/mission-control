"""Tests for osv_scanner_tool.py — summary parsing + subprocess mocking."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from sentinel_v2.tools.osv_scanner_tool import OsvScannerTool, _summarize


def _mock_proc(rc: int, stdout: str = "", stderr: str = ""):
    return MagicMock(returncode=rc, stdout=stdout, stderr=stderr)


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


def test_run_reports_missing_binary(tmp_path):
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value=None):
        result = OsvScannerTool()._run(scan_dir=str(tmp_path))
    data = json.loads(result)
    assert "error" in data
    assert "osv-scanner" in data["error"]


def test_run_rejects_nonexistent_dir(tmp_path):
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"):
        result = OsvScannerTool()._run(scan_dir=str(tmp_path / "missing"))
    data = json.loads(result)
    assert "error" in data
    assert "not a directory" in data["error"]


def test_run_parses_clean_scan(tmp_path):
    clean_json = json.dumps({"results": []})
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(0, clean_json),
         ):
        result = OsvScannerTool()._run(scan_dir=str(tmp_path))
    data = json.loads(result)
    assert data["total"] == 0
    assert data["scan_dir"] == str(tmp_path)


def test_run_parses_vulns_found(tmp_path):
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
        result = OsvScannerTool()._run(scan_dir=str(tmp_path))
    data = json.loads(result)
    assert data["total"] == 1
    assert data["counts"]["HIGH"] == 1
    assert data["findings"][0]["package"] == "lodash"


def test_run_handles_non_json_output(tmp_path):
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(0, "not json"),
         ):
        result = OsvScannerTool()._run(scan_dir=str(tmp_path))
    data = json.loads(result)
    assert "error" in data
    assert "not JSON" in data["error"]


def test_run_handles_timeout(tmp_path):
    import subprocess as _sp
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             side_effect=_sp.TimeoutExpired(cmd="osv-scanner", timeout=600),
         ):
        result = OsvScannerTool()._run(scan_dir=str(tmp_path))
    data = json.loads(result)
    assert "error" in data
    assert "timed out" in data["error"]


def test_run_handles_bad_rc(tmp_path):
    with patch("sentinel_v2.tools.osv_scanner_tool.shutil.which", return_value="/bin/osv-scanner"), \
         patch(
             "sentinel_v2.tools.osv_scanner_tool.subprocess.run",
             return_value=_mock_proc(127, "", "internal error"),
         ):
        result = OsvScannerTool()._run(scan_dir=str(tmp_path))
    data = json.loads(result)
    assert "error" in data
    assert "rc=127" in data["error"]
