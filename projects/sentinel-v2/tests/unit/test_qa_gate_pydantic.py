"""Tests for the QA gate's Pydantic-vs-legacy parsing in `_parse_deploy_result`.

Pins finding F1.4: when CrewAI returns a `QAGateReport` Pydantic instance
(via `output_pydantic` on the QA Lead task) the gate must read its fields
directly. The legacy string path is kept for back-compat with crews that
still emit JSON-as-text. Garbage output must produce an empty dict so the
QA gate at `sentinel_loop.py` fails closed.
"""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from sentinel_v2.crews.build_crew import QAGateReport
from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow


@pytest.fixture
def flow():
    return SentinelLoopFlow()


class TestQAGateReportSchema:
    """Pin the QAGateReport public contract."""

    def test_minimal_go_payload_validates(self):
        report = QAGateReport(go_no_go="GO", build_status="clean")
        assert report.go_no_go == "GO"
        assert report.build_status == "clean"
        assert report.blocking_issues == []
        assert report.notes is None

    def test_no_go_requires_blocking_issues_field_but_default_empty(self):
        report = QAGateReport(go_no_go="NO_GO", build_status="fail")
        assert report.go_no_go == "NO_GO"
        assert report.blocking_issues == []

    def test_invalid_go_no_go_literal_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QAGateReport(go_no_go="MAYBE", build_status="clean")

    def test_invalid_build_status_literal_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QAGateReport(go_no_go="GO", build_status="green")


class TestParseDeployResultPydanticPath:
    """Path 1 + 2 from the brief: structured QAGateReport on result.pydantic."""

    def test_pydantic_go_clean_returns_dict_for_gate(self, flow):
        report = QAGateReport(
            go_no_go="GO",
            build_status="clean",
            blocking_issues=[],
            notes="coverage 87%, smoke green",
        )
        result = Mock(spec=["pydantic", "raw"])
        result.pydantic = report
        result.raw = "natural-language prose the gate must ignore"

        parsed = flow._parse_deploy_result(result)

        assert parsed["go_no_go"] == "GO"
        assert parsed["build_status"] == "clean"
        assert parsed["blocking_issues"] == []
        assert parsed["notes"] == "coverage 87%, smoke green"

    def test_pydantic_no_go_fails_closed(self, flow):
        report = QAGateReport(
            go_no_go="NO_GO",
            build_status="fail",
            blocking_issues=["build broken: TS2322 in api.ts:42"],
        )
        result = Mock(spec=["pydantic", "raw"])
        result.pydantic = report
        result.raw = "{}"

        parsed = flow._parse_deploy_result(result)
        assert parsed["go_no_go"] == "NO_GO"
        assert parsed["build_status"] == "fail"
        assert parsed["blocking_issues"] == ["build broken: TS2322 in api.ts:42"]


class TestParseDeployResultLegacyPath:
    """Path 3 + 4 from the brief: legacy string output and garbage."""

    def test_legacy_string_json_go_clean_still_parses(self, flow):
        result = Mock(spec=["raw"])
        result.raw = (
            '{"go_no_go": "GO", "build_status": "clean", '
            '"blocking_issues": [], "coverage_percent": 82}'
        )

        parsed = flow._parse_deploy_result(result)

        assert parsed["go_no_go"] == "GO"
        assert parsed["build_status"] == "clean"
        assert parsed["blocking_issues"] == []

    def test_legacy_fenced_json_block_parses(self, flow):
        result = Mock(spec=["raw"])
        result.raw = (
            "Here is the QA report:\n\n"
            "```json\n"
            '{"go_no_go": "GO", "build_status": "warnings", "blocking_issues": []}\n'
            "```\n"
        )

        parsed = flow._parse_deploy_result(result)
        assert parsed["go_no_go"] == "GO"
        assert parsed["build_status"] == "warnings"

    def test_garbage_returns_empty_dict_so_gate_fails_closed(self, flow):
        result = Mock(spec=["raw"])
        result.raw = "I ran the build and it looked fine to me. Shipping it."

        parsed = flow._parse_deploy_result(result)

        assert parsed == {}

    def test_none_result_returns_empty_dict(self, flow):
        assert flow._parse_deploy_result(None) == {}
