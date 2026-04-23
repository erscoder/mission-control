"""
Approval State — shared JSON file for Telegram ↔ Flow communication.

Flow writes pending approval → file
Telegram callback reads/writes approval → file
Flow polls file to decide whether to proceed to deploy.

No Redis needed — just a JSON file with file locking.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_STATE_FILE = os.getenv("SENTION_APPROVAL_FILE", "/tmp/sentinel_v2_approval.json")


class ApprovalState:
    """
    Thread-safe JSON file store for approval state.

    Flow calls:
        state = ApprovalState()
        state.set_pending(cycle=3, summary="draft...", timestamp=...)
        while not state.is_approved(3):
            sleep(1)
        action = state.get_action(3)

    Telegram callback calls:
        state = ApprovalState()
        state.set_approved(cycle=3)   # or set_revision(3) or set_stop(3)
    """

    _lock = threading.Lock()

    def __init__(self, path: str | None = None):
        self._path = Path(path or _STATE_FILE)

    # ── Read helpers ────────────────────────────────────────────────────────

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict) -> None:
        self._path.write_text(json.dumps(data, indent=2))

    # ── Flow-side API ────────────────────────────────────────────────────────

    def set_pending(
        self,
        cycle: int,
        summary: str,
        timestamp: str | None = None,
        timeout_seconds: int = 3600,
    ) -> None:
        """Flow calls this when a draft needs approval."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._lock:
            data = self._read()
            data["pending"] = {
                "cycle": cycle,
                "summary": summary,
                "set_at": ts,
                "timeout_at": datetime.fromtimestamp(
                    datetime.now().timestamp() + timeout_seconds, tz=timezone.utc
                ).isoformat(),
                "action": None,
            }
            self._write(data)

    def is_approved(self, cycle: int) -> bool:
        """Returns True if this cycle has been approved (or auto-approved)."""
        with self._lock:
            data = self._read()
        pending = data.get("pending", {})
        if pending.get("cycle") != cycle:
            return False
        action = pending.get("action")
        if action in ("approved", "auto_approved"):
            return True
        # Check timeout
        timeout_at = pending.get("timeout_at")
        if timeout_at:
            try:
                if datetime.fromisoformat(timeout_at) < datetime.now(timezone.utc):
                    return True  # Auto-approve on timeout
            except (ValueError, OSError):
                pass
        return False

    def is_revison_requested(self, cycle: int) -> bool:
        """Returns True if Kike requested a revision for this cycle."""
        with self._lock:
            data = self._read()
        pending = data.get("pending", {})
        return pending.get("cycle") == cycle and pending.get("action") == "revision"

    def is_stop_requested(self) -> bool:
        """Returns True if Kike pressed the Stop button."""
        with self._lock:
            data = self._read()
        return data.get("stop", False)

    def get_action(self, cycle: int) -> Optional[str]:
        """Get the recorded action for a cycle (approved/revision/stop/timeout)."""
        with self._lock:
            data = self._read()
        pending = data.get("pending", {})
        if pending.get("cycle") != cycle:
            return None
        return pending.get("action")

    def clear_pending(self, cycle: int) -> None:
        """Clear pending state after it's been handled."""
        with self._lock:
            data = self._read()
        if data.get("pending", {}).get("cycle") == cycle:
            del data["pending"]
            self._write(data)

    def clear_all(self) -> None:
        """Clear all state (e.g., on shutdown)."""
        with self._lock:
            self._write({})

    # ── Telegram-side API ───────────────────────────────────────────────────

    def set_approved(self, cycle: int) -> None:
        """Telegram callback calls this when Kike approves."""
        with self._lock:
            data = self._read()
        pending = data.get("pending", {})
        if pending.get("cycle") == cycle:
            pending["action"] = "approved"
            pending["resolved_at"] = datetime.now(timezone.utc).isoformat()
            data["pending"] = pending
            self._write(data)

    def set_revision(self, cycle: int, notes: str = "") -> None:
        """Telegram callback calls this when Kike requests revision."""
        with self._lock:
            data = self._read()
        pending = data.get("pending", {})
        if pending.get("cycle") == cycle:
            pending["action"] = "revision"
            pending["revision_notes"] = notes
            pending["resolved_at"] = datetime.now(timezone.utc).isoformat()
            data["pending"] = pending
            self._write(data)

    def set_stop(self) -> None:
        """Telegram callback calls this when Kike presses Stop."""
        with self._lock:
            data = self._read()
        data["stop"] = True
        data["stopped_at"] = datetime.now(timezone.utc).isoformat()
        if "pending" in data:
            del data["pending"]
        self._write(data)

    def set_auto_approved(self, cycle: int) -> None:
        """Set auto-approved state (for demo/no-token mode)."""
        with self._lock:
            data = self._read()
        data["pending"] = {
            "cycle": cycle,
            "action": "auto_approved",
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write(data)
