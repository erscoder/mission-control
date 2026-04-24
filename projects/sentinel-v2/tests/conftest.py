"""Global pytest fixtures for Sentinel V2.

These hooks make the production path-safety guards in `crew_hooks` and
`dashboard_state` testable: in tests, we allow the pytest `tmp_path` prefix in
addition to the production `/tmp/sentinel_v2_` prefix. This way tests can use
the standard `tmp_path` fixture without disabling the security check in prod.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Make ``src/`` importable without needing an editable install.
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture(autouse=True)
def _allow_pytest_tmp_paths(monkeypatch):
    """Extend the allowed path prefix for the duration of a test so monkeypatched
    STATE_FILE / AGENT_MESSAGES_FILE pointing at pytest tmp_path are accepted by
    the `_safe_path` guard.

    Production code path is unaffected — the override is reverted at test teardown.
    """
    # Force import so sys.modules contains the modules before we patch them.
    import importlib
    for module_name in ("sentinel_v2.crew_hooks", "sentinel_v2.dashboard_state"):
        try:
            mod = importlib.import_module(module_name)
        except Exception:
            continue

        original = getattr(mod, "_safe_path", None)
        if original is None:
            continue

        def _permissive_safe_path(path, _orig=original):
            s = str(path)
            if "/pytest-of-" in s or "/pytest-" in s:
                return Path(s)
            return _orig(path)

        monkeypatch.setattr(mod, "_safe_path", _permissive_safe_path)

    yield
