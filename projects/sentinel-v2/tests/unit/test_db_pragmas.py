"""Pin SQLite pragmas applied by db.connect().

WAL + busy_timeout=30000 + synchronous=NORMAL are the concurrency-safe defaults
required by F3.3 to keep the daemon and the dashboard from tripping
"database is locked" while sharing sentinel.db.
"""
from __future__ import annotations

import sqlite3

import pytest

from sentinel_v2 import db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect every test to a fresh sentinel.db under tmp_path."""
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "test.db"))
    db._initialized = False
    yield
    db._initialized = False


class TestPragmasOnConnect:
    def test_journal_mode_is_wal(self):
        with db.connect() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_busy_timeout_is_30000(self):
        with db.connect() as conn:
            timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == 30000

    def test_synchronous_is_normal(self):
        with db.connect() as conn:
            # synchronous returns an int: 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA.
            sync = conn.execute("PRAGMA synchronous").fetchone()[0]
        assert sync == 1

    def test_pragmas_reapplied_on_each_connection(self):
        """busy_timeout and synchronous are per-connection. A second connect()
        on the same DB file must still land them, not rely on the first call."""
        with db.connect():
            pass
        with db.connect() as conn:
            timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            sync = conn.execute("PRAGMA synchronous").fetchone()[0]
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert timeout == 30000
        assert sync == 1
        assert mode.lower() == "wal"

    def test_connect_uses_30s_python_timeout(self, monkeypatch):
        """The Python-level sqlite3.connect timeout must be 30 seconds so that
        the C-side default lock wait matches the busy_timeout we set."""
        captured: dict = {}
        real_connect = sqlite3.connect

        def spy(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return real_connect(*args, **kwargs)

        monkeypatch.setattr(db.sqlite3, "connect", spy)
        with db.connect():
            pass
        assert captured["timeout"] == 30.0
