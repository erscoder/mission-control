"""Unit tests for sentinel_v2.db — SQLite draft persistence."""
from __future__ import annotations

import pytest

from sentinel_v2 import db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect every test to a fresh sentinel.db under tmp_path."""
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "test.db"))
    # Reset the module-level init flag so the new file gets its schema.
    db._initialized = False
    yield
    db._initialized = False


class TestUpsertAndGet:
    def test_creates_new_draft(self):
        db.upsert_draft(
            "draft-1",
            cycle=1,
            title="Alpha",
            status="pending",
            opportunity={"problem": "x", "tags": ["a"]},
        )
        d = db.get("draft-1")
        assert d["title"] == "Alpha"
        assert d["status"] == "pending"
        assert d["cycle"] == 1
        assert d["problem"] == "x"
        assert d["tags"] == ["a"]

    def test_upsert_updates_existing(self):
        db.upsert_draft("d", cycle=1, title="Old", status="pending")
        db.upsert_draft("d", cycle=1, title="New", status="queued")
        got = db.get("d")
        assert got["title"] == "New"
        assert got["status"] == "queued"

    def test_get_missing_returns_none(self):
        assert db.get("missing") is None


class TestPatchPhase:
    def test_merges_phase_payload(self):
        db.upsert_draft("d", cycle=1, title="T", status="pending")
        assert db.patch_phase("d", "build_info", {"build_progress": 0.5}) is True
        assert db.patch_phase("d", "build_info", {"tests_passed": 10}) is True
        out = db.get("d")
        assert out["build_progress"] == 0.5
        assert out["tests_passed"] == 10

    def test_unknown_phase_raises(self):
        db.upsert_draft("d", cycle=1, title="T", status="pending")
        with pytest.raises(ValueError):
            db.patch_phase("d", "not_a_phase", {"x": 1})

    def test_missing_draft_returns_false(self):
        assert db.patch_phase("nope", "match_info", {"score": 1.0}) is False


class TestSetStatus:
    def test_updates_status(self):
        db.upsert_draft("d", cycle=1, title="T", status="pending")
        assert db.set_status("d", "queued") is True
        assert db.get("d")["status"] == "queued"

    def test_sets_revision_notes(self):
        db.upsert_draft("d", cycle=1, title="T", status="pending")
        db.set_status("d", "pending", revision_notes="try smaller scope")
        assert db.get("d")["revision_notes"] == "try smaller scope"

    def test_missing_draft_returns_false(self):
        assert db.set_status("nope", "queued") is False


class TestList:
    def test_list_all(self):
        db.upsert_draft("d1", cycle=1, title="A", status="pending")
        db.upsert_draft("d2", cycle=2, title="B", status="queued")
        ids = {d["id"] for d in db.list_all()}
        assert ids == {"d1", "d2"}

    def test_list_by_status(self):
        db.upsert_draft("d1", cycle=1, title="A", status="pending")
        db.upsert_draft("d2", cycle=2, title="B", status="queued")
        db.upsert_draft("d3", cycle=3, title="C", status="deployed")
        queued = db.list_by_status({"queued", "deployed"})
        assert {d["id"] for d in queued} == {"d2", "d3"}

    def test_list_by_status_empty_set(self):
        db.upsert_draft("d1", cycle=1, title="A", status="pending")
        assert db.list_by_status(set()) == []


class TestRowShape:
    def test_stable_cols_override_phase_json(self):
        """If a phase blob accidentally contains a stable field, the column wins."""
        db.upsert_draft("d", cycle=1, title="Real", status="pending")
        # Poison the opportunity blob with a bogus title.
        db.patch_phase("d", "opportunity", {"title": "STALE", "status": "STALE"})
        out = db.get("d")
        assert out["title"] == "Real"
        assert out["status"] == "pending"
