"""Tests for the ``infra_state`` key/value table in db.py.

Pins the contract used by ``flows.shared_postgres`` to remember the shared
Fly Postgres cluster name across container restarts. The first deploy that
spins up the cluster persists the name here; subsequent deploys read it back
and skip the ``fly postgres create`` call entirely.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_v2 import db


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point sentinel db at a fresh sqlite file and reset the init guard.

    Without resetting ``db._initialized`` the schema-create branch is skipped
    on a brand new file because the import-time singleton already fired
    against the production sentinel.db.
    """
    db_file = tmp_path / "test_sentinel.db"
    monkeypatch.setenv("SENTINEL_DB_PATH", str(db_file))
    monkeypatch.setattr(db, "_initialized", False)
    return db_file


class TestInfraStateCrud:
    def test_get_returns_none_for_missing_key(self, temp_db: Path) -> None:
        assert db.get_infra("never_set") is None

    def test_set_then_get_roundtrips(self, temp_db: Path) -> None:
        db.set_infra("shared_pg_cluster_name", "sentinel-shared-pg")
        assert db.get_infra("shared_pg_cluster_name") == "sentinel-shared-pg"

    def test_set_overwrites_on_conflict(self, temp_db: Path) -> None:
        db.set_infra("shared_pg_cluster_region", "fra")
        db.set_infra("shared_pg_cluster_region", "iad")
        assert db.get_infra("shared_pg_cluster_region") == "iad"

    def test_delete_returns_one_when_present(self, temp_db: Path) -> None:
        db.set_infra("k", "v")
        assert db.delete_infra("k") == 1
        assert db.get_infra("k") is None

    def test_delete_returns_zero_when_absent(self, temp_db: Path) -> None:
        assert db.delete_infra("never_set") == 0

    def test_table_isolated_from_drafts(self, temp_db: Path) -> None:
        # Sanity: writing infra_state must not affect the drafts table.
        db.set_infra("k", "v")
        with db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
        assert count == 0
