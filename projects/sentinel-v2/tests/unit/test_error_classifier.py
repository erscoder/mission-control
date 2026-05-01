"""Unit tests for sentinel_v2.flows.error_classifier."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel_v2.flows.error_classifier import (
    ACTION_HINTS,
    RECOVERABLE_PATTERNS,
    classify_error,
    is_transient,
    write_escalation,
)


class TestClassifyError:
    """Pattern matching for error categories."""

    def test_none_for_empty_input(self):
        assert classify_error("") is None
        assert classify_error(None) is None  # type: ignore[arg-type]

    def test_none_for_recoverable_error(self):
        # Code-shaped errors must NOT classify as blocked
        recoverable = [
            "ERESOLVE unable to resolve dependency tree",
            "TypeError: Cannot read property 'foo' of undefined",
            "Error: Module not found: 'lodash'",
            "npm ERR! peer dep missing: react@^18",
            "Test failed: expected 200 got 500",
        ]
        for msg in recoverable:
            assert classify_error(msg) is None, f"False positive on: {msg!r}"

    @pytest.mark.parametrize(
        "msg",
        [
            "Error code: 429 - Rate limit exceeded",
            "HTTP 429 Too Many Requests",
            "rate_limit_error from provider",
            "rate-limit hit, retry later",
            "Quota exceeded for the day",
            "You have exceeded your usage limit",
        ],
    )
    def test_classifies_quota(self, msg):
        assert classify_error(msg) == "blocked_quota"

    @pytest.mark.parametrize(
        "msg",
        [
            "401 Unauthorized",
            "HTTP 403 Forbidden",
            "invalid_api_key supplied",
            "Authentication failed for provider",
            "Token expired, please re-login",
            "expired token returned by upstream",
        ],
    )
    def test_classifies_auth(self, msg):
        assert classify_error(msg) == "blocked_auth"

    @pytest.mark.parametrize(
        "msg",
        [
            "402 Payment Required",
            "Payment required to continue",
            "Insufficient balance on the account",
            "insufficient funds for this operation",
            "Billing issue: please update payment method",
        ],
    )
    def test_classifies_payment(self, msg):
        assert classify_error(msg) == "blocked_payment"

    def test_classifies_token_plan_specific(self):
        msg = (
            "Error code: 429 - {'type': 'error', 'error': "
            "{'message': 'The Token Plan is designed for individual, "
            "interactive developer workflows.'}}"
        )
        # token_plan patterns appear before generic 429 in ESCALATION_PATTERNS,
        # so the more specific category wins
        assert classify_error(msg) == "blocked_token_plan"

    def test_action_hints_cover_all_categories(self):
        # Every category produced by classify_error must have an action hint
        # so the escalation file is always actionable for the operator.
        seen = {
            classify_error("429"),
            classify_error("401"),
            classify_error("402"),
            classify_error("token plan is designed"),
        }
        seen.discard(None)
        for category in seen:
            assert category in ACTION_HINTS, f"Missing hint for {category}"


class TestIsTransient:
    """Transient-network short-circuit (F2.1)."""

    def test_false_for_empty_input(self):
        assert is_transient("") is False
        assert is_transient(None) is False  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "msg",
        [
            "connect ECONNREFUSED 127.0.0.1:5432",
            "Error: read ECONNRESET",
            "request to https://registry.npmjs.org failed, ETIMEDOUT",
            "Error: socket hang up",
            "getaddrinfo ENOTFOUND registry.npmjs.org",
            "Error: read timeout after 30000ms",
            "connect EHOSTUNREACH: network is unreachable",
            "Operation timed out after 60s",
        ],
    )
    def test_recognises_each_transient_pattern(self, msg):
        assert is_transient(msg) is True
        # And classify_error must NOT escalate on a transient hit.
        assert classify_error(msg) is None

    @pytest.mark.parametrize(
        "msg",
        [
            "ERESOLVE unable to resolve dependency tree",
            "TypeError: Cannot read property 'foo' of undefined",
            "npm ERR! peer dep missing: react@^18",
        ],
    )
    def test_recoverable_code_errors_are_not_transient(self, msg):
        # Code-shaped errors must NOT be flagged as transient and must NOT
        # escalate (regression guard around the false-positive surface).
        assert is_transient(msg) is False
        assert classify_error(msg) is None

    def test_quota_still_escalates_when_no_transient_overlap(self):
        # Regression: real escalation patterns keep escalating after the
        # transient short-circuit was added.
        assert classify_error("HTTP 429 Too Many Requests") == "blocked_quota"
        assert classify_error("401 Unauthorized") == "blocked_auth"
        assert classify_error("402 Payment Required") == "blocked_payment"

    def test_transient_overlap_wins_over_escalation(self):
        # Option A contract: when an error string matches both a transient
        # pattern AND an escalation pattern, transient wins so we retry
        # without burning the operator's escalation budget.
        msg = "429 from registry, request timed out after 30s"
        assert is_transient(msg) is True
        assert classify_error(msg) is None

    def test_recoverable_patterns_share_single_category(self):
        # Documents the design choice: every recoverable pattern is filed
        # under "transient_network" so callers can branch on a single tag.
        categories = {category for category, _ in RECOVERABLE_PATTERNS}
        assert categories == {"transient_network"}


class TestWriteEscalation:
    """Escalation file writes are append-only and resilient."""

    @pytest.fixture
    def escalation_file(self, tmp_path, monkeypatch):
        path = tmp_path / "escalations.json"
        monkeypatch.setattr(
            "sentinel_v2.flows.error_classifier.ESCALATION_FILE", path
        )
        return path

    def test_creates_file_with_first_entry(self, escalation_file):
        write_escalation(
            "blocked_quota",
            "Rate limit hit",
            phase="build",
            draft_id="draft_c1_foo",
            cycle=3,
        )
        data = json.loads(escalation_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        entry = data[0]
        assert entry["category"] == "blocked_quota"
        assert entry["phase"] == "build"
        assert entry["draft_id"] == "draft_c1_foo"
        assert entry["cycle"] == 3
        assert "Rate limit hit" in entry["error_excerpt"]
        assert entry["action_required"] == ACTION_HINTS["blocked_quota"]
        assert "timestamp" in entry

    def test_appends_to_existing_list(self, escalation_file):
        escalation_file.write_text(json.dumps([{"category": "old"}]))
        write_escalation(
            "blocked_auth", "401", phase="deploy", draft_id="d2", cycle=4
        )
        data = json.loads(escalation_file.read_text())
        assert len(data) == 2
        assert data[0]["category"] == "old"
        assert data[1]["category"] == "blocked_auth"

    def test_recovers_from_corrupt_file(self, escalation_file):
        escalation_file.write_text("not valid json {{{")
        write_escalation(
            "blocked_quota", "429", phase="build", draft_id="d3", cycle=5
        )
        data = json.loads(escalation_file.read_text())
        assert len(data) == 1
        assert data[0]["category"] == "blocked_quota"

    def test_truncates_long_error(self, escalation_file):
        huge = "x" * 5000
        write_escalation(
            "blocked_auth", huge, phase="build", draft_id=None, cycle=1
        )
        data = json.loads(escalation_file.read_text())
        assert len(data[0]["error_excerpt"]) == 2048

    def test_extra_context_preserved(self, escalation_file):
        write_escalation(
            "blocked_quota",
            "429",
            phase="deploy",
            draft_id="d4",
            cycle=2,
            extra={"attempt": 1, "slug": "compliancedesk"},
        )
        data = json.loads(escalation_file.read_text())
        assert data[0]["extra"] == {"attempt": 1, "slug": "compliancedesk"}
