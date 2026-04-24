"""Unit tests for CRITICAL fix 2: Path validation in crew_hooks.py and dashboard_state.py"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sentinel_v2.crew_hooks import _safe_path, _sanitize_agent_id
from sentinel_v2.dashboard_state import _safe_path as dashboard_safe_path, _sanitize_agent_id as dashboard_sanitize_agent_id


def test_safe_path_valid():
    """Test path validation with valid paths"""
    valid_paths = [
        "/tmp/sentinel_v2_state.json",
        "/tmp/sentinel_v2_agent_messages.json",
        "/tmp/sentinel_v2_flow_breakdown.json",
        "/tmp/sentinel_v2_test.json",
    ]

    for p in valid_paths:
        result = _safe_path(p)
        assert str(result) == p, f"Valid path should be unchanged: {p}"

    print("✅ test_safe_path_valid: PASSED")


def test_safe_path_traversal():
    """Test path validation rejects path traversal attacks"""
    unsafe_paths = [
        "/tmp/sentinel_v2_../../../etc/passwd",
        "/tmp/sentinel_v2../test.json",
        "/tmp/sentinel_v2_../../../../etc/hosts",
        "../sentinel_v2_test.json",
        "/tmp/../../../tmp/sentinel_v2_test.json",
    ]

    for p in unsafe_paths:
        try:
            _safe_path(p)
            assert False, f"Should reject path traversal: {p}"
        except ValueError as e:
            assert "path traversal" in str(e).lower(), f"Expected path traversal error for {p}"

    print("✅ test_safe_path_traversal: PASSED")


def test_safe_path_invalid_prefix():
    """Test path validation rejects paths outside allowed prefix"""
    unsafe_paths = [
        "/tmp/evil_state.json",
        "/tmp/sentinel_evil_test.json",
        "/var/tmp/sentinel_v2_test.json",
        "/tmp_other/sentinel_v2_test.json",
    ]

    for p in unsafe_paths:
        try:
            _safe_path(p)
            assert False, f"Should reject path with wrong prefix: {p}"
        except ValueError as e:
            assert "must start with" in str(e).lower(), f"Expected prefix error for {p}"

    print("✅ test_safe_path_invalid_prefix: PASSED")


def test_safe_path_invalid_chars():
    """Test path validation rejects suspicious characters"""
    unsafe_paths = [
        "/tmp/sentinel_v2_test(1).json",
        "/tmp/sentinel_v2_test[a].json",
        "/tmp/sentinel_v2_test{b}.json",
        "/tmp/sentinel_v2_test;c=1.json",
        "/tmp/sentinel_v2_test`cmd`.json",
        "/tmp/sentinel_v2_test$VAR.json",
    ]

    for p in unsafe_paths:
        try:
            _safe_path(p)
            assert False, f"Should reject path with invalid chars: {p}"
        except ValueError as e:
            assert "invalid characters" in str(e).lower(), f"Expected invalid chars error for {p}"

    print("✅ test_safe_path_invalid_chars: PASSED")


def test_sanitize_agent_id():
    """Test agent_id sanitization"""
    tests = [
        ("web-scout", "web-scout"),
        ("Web Scout", "web-scout"),
        ("Security Engineer", "security-engineer"),
        ("QA Lead", "qa-lead"),
        ("agent/with/slashes", "agentwithslashes"),
        ("agent:with:colons", "agentwithcolons"),
        ("agent_with.at.dots", "agentwithatdots"),
        ("agent with multiple   spaces", "agent-with-multiple-spaces"),
        ("Agent123", "agent123"),
        ("", "unknown"),
    ]

    for input_id, expected in tests:
        result = _sanitize_agent_id(input_id)
        assert result == expected, f"Expected '{expected}' but got '{result}' for input '{input_id}'"

    print("✅ test_sanitize_agent_id: PASSED")


def test_dashboard_safe_path_consistency():
    """Test dashboard_state.py has same path validation as crew_hooks.py"""
    valid = "/tmp/sentinel_v2_test.json"
    assert str(_safe_path(valid)) == str(dashboard_safe_path(valid))

    unsafe = "/tmp/sentinel_v2_../../../etc/passwd"
    try:
        _safe_path(unsafe)
        crew_error = None
    except ValueError as e:
        crew_error = e

    try:
        dashboard_safe_path(unsafe)
        dashboard_error = None
    except ValueError as e:
        dashboard_error = e

    # Both should raise ValueError
    assert crew_error is not None, "crew_hooks should reject path traversal"
    assert dashboard_error is not None, "dashboard_state should reject path traversal"

    print("✅ test_dashboard_safe_path_consistency: PASSED")


def test_dashboard_sanitize_agent_id_consistency():
    """Test dashboard_state.py has same sanitization as crew_hooks.py"""
    test_id = "Web Scout (Profile)"
    assert _sanitize_agent_id(test_id) == dashboard_sanitize_agent_id(test_id)

    test_id2 = "QA/Lead-Test"
    assert _sanitize_agent_id(test_id2) == dashboard_sanitize_agent_id(test_id2)

    print("✅ test_dashboard_sanitize_agent_id_consistency: PASSED")


if __name__ == "__main__":
    test_safe_path_valid()
    test_safe_path_traversal()
    test_safe_path_invalid_prefix()
    test_safe_path_invalid_chars()
    test_sanitize_agent_id()
    test_dashboard_safe_path_consistency()
    test_dashboard_sanitize_agent_id_consistency()

    print("\n✅ All path validation tests PASSED!")
