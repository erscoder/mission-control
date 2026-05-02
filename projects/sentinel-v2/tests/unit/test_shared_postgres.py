"""Tests for ``flows.shared_postgres`` cluster + per-app DB attach helpers.

All ``flyctl`` shell-outs are mocked. Tests focus on:
  - Idempotency: state recorded -> skip flyctl entirely.
  - Recovery: state empty but cluster exists on Fly -> record + skip create.
  - Create path: state empty + cluster missing -> create + record.
  - Attach: parses DATABASE_URL, handles already-attached, surfaces failure.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from sentinel_v2 import db
from sentinel_v2.flows import shared_postgres


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_file = tmp_path / "test_sentinel.db"
    monkeypatch.setenv("SENTINEL_DB_PATH", str(db_file))
    monkeypatch.setattr(db, "_initialized", False)
    return db_file


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _fail(stdout: str = "", stderr: str = "", rc: int = 1) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


class TestEnsureSharedPgCluster:
    def test_state_recorded_short_circuits_flyctl(self, temp_db: Path) -> None:
        db.set_infra("shared_pg_cluster_name", "sentinel-shared-pg")
        db.set_infra("shared_pg_cluster_region", "fra")

        with patch("sentinel_v2.flows.shared_postgres._run_fly") as mock_run:
            result = shared_postgres.ensure_shared_pg_cluster()

        mock_run.assert_not_called()
        assert result["cluster_name"] == "sentinel-shared-pg"
        assert result["region"] == "fra"
        assert result["created"] is False
        assert result["source"] == "state"

    def test_recovers_existing_cluster_via_fly_list(self, temp_db: Path) -> None:
        # State empty but Fly already has the cluster (e.g. dev recreated the
        # sentinel.db file). Must record and not call create.
        list_out = "NAME                ORG    REGION\nsentinel-shared-pg  ers    fra"
        with patch(
            "sentinel_v2.flows.shared_postgres._run_fly",
            return_value=_ok(stdout=list_out),
        ) as mock_run:
            result = shared_postgres.ensure_shared_pg_cluster()

        # Only the list call. No create call.
        assert mock_run.call_count == 1
        assert mock_run.call_args.args[0:2] == ("postgres", "list")
        assert result["created"] is False
        assert result["source"] == "list"
        assert db.get_infra("shared_pg_cluster_name") == "sentinel-shared-pg"

    def test_creates_cluster_when_missing_on_fly(self, temp_db: Path) -> None:
        # Sequence: list -> empty -> create -> ok.
        responses = [
            _ok(stdout="NAME    ORG    REGION\n"),
            _ok(stdout="Postgres cluster sentinel-shared-pg created"),
        ]

        def side_effect(*args, **kwargs):
            return responses.pop(0)

        with patch("sentinel_v2.flows.shared_postgres._run_fly", side_effect=side_effect) as mock_run:
            result = shared_postgres.ensure_shared_pg_cluster(region="fra")

        assert result["created"] is True
        assert result["source"] == "created"
        # Two flyctl calls: list, create.
        assert mock_run.call_count == 2
        create_args = mock_run.call_args_list[1].args
        assert create_args[0:2] == ("postgres", "create")
        assert "--name" in create_args
        assert "--region" in create_args
        # Recorded in infra_state for next time.
        assert db.get_infra("shared_pg_cluster_name") == "sentinel-shared-pg"
        assert db.get_infra("shared_pg_cluster_region") == "fra"

    def test_create_already_taken_treated_as_success(self, temp_db: Path) -> None:
        # Race: list said missing but create returns "already taken". Don't crash.
        responses = [
            _ok(stdout=""),
            _fail(stderr="App name already taken: sentinel-shared-pg"),
        ]

        def side_effect(*args, **kwargs):
            return responses.pop(0)

        with patch("sentinel_v2.flows.shared_postgres._run_fly", side_effect=side_effect):
            result = shared_postgres.ensure_shared_pg_cluster()

        assert result["created"] is True
        assert db.get_infra("shared_pg_cluster_name") == "sentinel-shared-pg"

    def test_create_genuine_failure_raises(self, temp_db: Path) -> None:
        responses = [
            _ok(stdout=""),
            _fail(stderr="payment required: top up balance"),
        ]

        def side_effect(*args, **kwargs):
            return responses.pop(0)

        with patch("sentinel_v2.flows.shared_postgres._run_fly", side_effect=side_effect), \
             pytest.raises(RuntimeError) as excinfo:
            shared_postgres.ensure_shared_pg_cluster()

        assert "payment required" in str(excinfo.value).lower()
        assert db.get_infra("shared_pg_cluster_name") is None  # not recorded


class TestAttachDbForApp:
    def test_returns_database_url_on_success(self) -> None:
        out = (
            "Attaching cluster sentinel-shared-pg to app foo-api\n"
            "Postgres cluster sentinel-shared-pg is now attached to foo-api\n"
            "The following secret was added to foo-api:\n"
            "  DATABASE_URL=postgres://foo_api_user:hunter2@top1.nearest.of.sentinel-shared-pg.internal:5432/foo_api_db\n"
        )
        with patch(
            "sentinel_v2.flows.shared_postgres._run_fly",
            return_value=_ok(stdout=out),
        ):
            info = shared_postgres.attach_db_for_app(
                cluster_name="sentinel-shared-pg",
                backend_app_name="foo-api",
            )
        assert info["already_attached"] is False
        assert info["database_url"].startswith("postgres://foo_api_user:")
        assert info["database_name"] == "foo_api_db"
        assert info["database_user"] == "foo_api_user"

    def test_already_attached_returns_marker_no_url(self) -> None:
        # Fly returns rc=1 with a notice; helper translates to already_attached=True.
        out = "App foo-api is already attached to Postgres cluster sentinel-shared-pg"
        with patch("sentinel_v2.flows.shared_postgres._run_fly") as mock_run:
            mock_run.side_effect = [
                _fail(stderr=out),
                _ok(stdout="DATABASE_URL    abc123    2026-05-02"),  # secrets list
            ]
            info = shared_postgres.attach_db_for_app(
                cluster_name="sentinel-shared-pg",
                backend_app_name="foo-api",
            )
        assert info["already_attached"] is True
        # URL is empty string (set on app, value not visible) or None.
        assert info["database_url"] in ("", None)

    def test_attach_genuine_failure_raises(self) -> None:
        with patch(
            "sentinel_v2.flows.shared_postgres._run_fly",
            return_value=_fail(stderr="cluster not found", rc=1),
        ), pytest.raises(RuntimeError) as excinfo:
            shared_postgres.attach_db_for_app(
                cluster_name="missing",
                backend_app_name="foo-api",
            )
        assert "cluster not found" in str(excinfo.value).lower()


class TestParseDatabaseUrl:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("DATABASE_URL=postgres://u:p@h:5432/db", "postgres://u:p@h:5432/db"),
            ("connection: postgresql://u:p@h/d", "postgresql://u:p@h/d"),
            ("no url here", None),
            ("", None),
        ],
    )
    def test_extracts_first_url(self, text: str, expected) -> None:
        assert shared_postgres._parse_database_url(text) == expected
