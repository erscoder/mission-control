"""SQLite persistence for Sentinel V2 drafts/projects.

Single source of truth for the project lifecycle. Schema is hybrid:
- Stable columns for fields the dashboard queries/sorts on (id, cycle, status, title, timestamps).
- Per-phase JSON blobs so each phase can contribute arbitrary data without schema churn.

Writer/reader contract:
- Python Sentinel flow is the creator (research phase) and the phase-progress writer.
- Flask dashboard is a reader + status-flipper (approve/reject/deploy).
- sqlite3 stdlib, WAL mode, busy_timeout — handles concurrent access.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "sentinel.db"


def _db_path() -> Path:
    override = os.getenv("SENTINEL_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


_SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
    id              TEXT PRIMARY KEY,
    cycle           INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    title           TEXT NOT NULL,
    opportunity     TEXT,   -- JSON: research-phase payload (icp, demand_signals, kill_risks, etc.)
    match_info      TEXT,   -- JSON: match_score, user_profile, tech_fit
    build_info      TEXT,   -- JSON: build_output, coverage, tests, issues, progress
    deploy_info     TEXT,   -- JSON: deployment_url, deployment_id
    revision_notes  TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);
CREATE INDEX IF NOT EXISTS idx_drafts_cycle  ON drafts(cycle);

CREATE TABLE IF NOT EXISTS flow_checkpoints (
    draft_id   TEXT PRIMARY KEY,
    phase      TEXT NOT NULL,
    state_json TEXT NOT NULL,
    saved_at   TEXT NOT NULL
);
"""

_init_lock = threading.Lock()
_initialized = False


def _ensure_schema(conn: sqlite3.Connection) -> None:
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        conn.executescript("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;")
        conn.executescript(_SCHEMA)
        conn.commit()
        _initialized = True


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a short-lived connection. Callers should use this as a context manager."""
    conn = sqlite3.connect(_db_path(), isolation_level=None, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        _ensure_schema(conn)
        yield conn
    finally:
        conn.close()


# ── Row helpers ──────────────────────────────────────────────────────────────

_PHASE_KEYS = ("opportunity", "match_info", "build_info", "deploy_info")


def _loads(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _row_to_draft(row: sqlite3.Row) -> dict:
    """Flatten a DB row into the dict shape the dashboard expects.

    Phase JSON blobs are spread at the top level, then stable columns override them
    so status/title/cycle are never shadowed by stale nested values.
    """
    data: dict[str, Any] = {}
    for key in _PHASE_KEYS:
        data.update(_loads(row[key]))
    data.update(
        {
            "id": row["id"],
            "cycle": row["cycle"],
            "status": row["status"],
            "title": row["title"],
            "revision_notes": row["revision_notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    )
    return data


# ── CRUD ─────────────────────────────────────────────────────────────────────


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_draft(
    draft_id: str,
    *,
    cycle: int,
    title: str,
    status: str,
    opportunity: dict | None = None,
) -> None:
    """Create or replace a draft at research time.

    Subsequent phases should call :func:`patch_phase` to add their contributions
    rather than overwriting the whole draft.
    """
    now = now_iso()
    opp_json = json.dumps(opportunity) if opportunity else None
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO drafts (id, cycle, status, title, opportunity, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                cycle = excluded.cycle,
                title = excluded.title,
                status = excluded.status,
                opportunity = COALESCE(excluded.opportunity, drafts.opportunity),
                updated_at = excluded.updated_at
            """,
            (draft_id, cycle, status, title, opp_json, now, now),
        )


def patch_phase(draft_id: str, phase: str, payload: dict) -> bool:
    """Merge `payload` into the named phase JSON blob. Returns False if draft missing."""
    if phase not in _PHASE_KEYS:
        raise ValueError(f"unknown phase: {phase}")
    with connect() as conn:
        row = conn.execute(
            f"SELECT {phase} FROM drafts WHERE id = ?", (draft_id,)
        ).fetchone()
        if row is None:
            return False
        merged = _loads(row[phase])
        merged.update(payload)
        conn.execute(
            f"UPDATE drafts SET {phase} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(merged), now_iso(), draft_id),
        )
    return True


def set_status(draft_id: str, status: str, *, revision_notes: str | None = None) -> bool:
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE drafts
               SET status = ?,
                   revision_notes = COALESCE(?, revision_notes),
                   updated_at = ?
             WHERE id = ?
            """,
            (status, revision_notes, now_iso(), draft_id),
        )
        return cur.rowcount > 0


def get(draft_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        return _row_to_draft(row) if row else None


def list_all() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM drafts ORDER BY created_at ASC"
        ).fetchall()
        return [_row_to_draft(r) for r in rows]


def save_flow_checkpoint(draft_id: str, phase: str, state_json: str) -> None:
    """Upsert the in-progress flow state so the daemon can resume on restart."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO flow_checkpoints (draft_id, phase, state_json, saved_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(draft_id) DO UPDATE SET
                phase      = excluded.phase,
                state_json = excluded.state_json,
                saved_at   = excluded.saved_at
            """,
            (draft_id, phase, state_json, now_iso()),
        )


def load_active_flow_checkpoint() -> str | None:
    """Return the state_json of the most recent checkpoint, or None."""
    with connect() as conn:
        row = conn.execute(
            "SELECT state_json FROM flow_checkpoints ORDER BY saved_at DESC LIMIT 1"
        ).fetchone()
        return row["state_json"] if row else None


def clear_flow_checkpoint(draft_id: str) -> None:
    """Remove checkpoint when cycle completes or is abandoned."""
    with connect() as conn:
        conn.execute("DELETE FROM flow_checkpoints WHERE draft_id = ?", (draft_id,))


def list_by_status(statuses: set[str]) -> list[dict]:
    if not statuses:
        return []
    placeholders = ",".join("?" * len(statuses))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM drafts WHERE status IN ({placeholders}) ORDER BY created_at ASC",
            tuple(statuses),
        ).fetchall()
        return [_row_to_draft(r) for r in rows]
