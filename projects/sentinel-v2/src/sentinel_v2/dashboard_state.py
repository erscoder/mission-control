"""
Dashboard state manager for Sentinel V2.

Tracks flow state and agent messages for the real-time dashboard.
Now includes granular FlowBreakdown for detailed phase tracking.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


STATE_FILE = Path("/tmp/sentinel_v2_state.json")
AGENT_MESSAGES_FILE = Path("/tmp/sentinel_v2_agent_messages.json")
DRAFTS_FILE = Path("/tmp/sentinel_v2_drafts.json")

# ── Path Validation ──────────────────────────────────────────────────────────

ALLOWED_TMP_PREFIX = "/tmp/sentinel_v2_"


def _safe_path(path: Path | str) -> Path:
    """
    Validate and sanitize a path to prevent path traversal attacks.
    
    Rules:
    - Only allows paths under /tmp/sentinel_v2_*
    - Rejects paths containing ".." (parent directory traversal)
    - Rejects paths with suspicious characters like parentheses
    - Agent IDs are sanitized before use in paths
    
    Args:
        path: Path to validate
        
    Returns:
        Validated Path object
        
    Raises:
        ValueError: If path is unsafe or outside allowed directory
    """
    path_str = str(path)
    
    # Check for path traversal attempts
    if ".." in path_str:
        raise ValueError(f"Path traversal attempt detected: {path_str}")
    
    # Must start with allowed prefix
    if not path_str.startswith(ALLOWED_TMP_PREFIX):
        raise ValueError(f"Path must start with {ALLOWED_TMP_PREFIX}: {path_str}")
    
    # Reject suspicious characters (parentheses, newlines in paths)
    # Allow alphanumeric, dash, underscore, dot, slash
    if not re.match(r"^[\w\-./]+$", path_str):
        raise ValueError(f"Path contains invalid characters: {path_str}")
    
    return Path(path_str)


def _sanitize_agent_id(agent_id: str) -> str:
    """Sanitize an agent_id for safe use in file paths.

    Spaces collapse to dashes; only lowercase alphanumerics and dashes survive.
    Kept consistent with crew_hooks._sanitize_agent_id.
    """
    sanitized = agent_id.lower().replace(" ", "-")
    sanitized = re.sub(r"[^a-z0-9\-]", "", sanitized)
    sanitized = re.sub(r"-+", "-", sanitized)
    sanitized = sanitized.strip("-")
    return sanitized or "unknown"


# ── Flow Breakdown Schema ─────────────────────────────────────────────────────


class FlowBlocker(BaseModel):
    """A blocker preventing progress."""
    id: str
    description: str
    severity: str = "medium"  # low, medium, high, critical
    created_at: str
    resolved: bool = False


class FlowMetrics(BaseModel):
    """Metrics for the current phase."""
    coverage_percent: float = 0.0
    issues_count: int = 0
    files_changed: int = 0
    tests_passed: int = 0
    tests_total: int = 0
    custom: dict[str, Any] = {}


class FlowTask(BaseModel):
    """A task within a sub-phase."""
    id: str
    description: str
    status: str = "pending"  # pending, running, done, blocked, skipped
    completed_at: str | None = None


class FlowSubPhase(BaseModel):
    """A sub-phase within a phase."""
    id: str  # e.g. "code-review-phase-1"
    name: str
    status: str = "pending"  # pending, running, done, blocked, skipped
    progress: float = 0.0  # 0.0 - 1.0
    current_task: str | None = None
    completed_tasks: list[str] = []
    pending_tasks: list[str] = []


class FlowBreakdown(BaseModel):
    """
    Granular flow state broken down into cycles, phases, and sub-phases.
    
    Used by the dashboard Flow State Panel for detailed progress visualization.
    """
    cycle: int = 0
    phase: str = "idle"
    sub_phase: str | None = None
    status: str = "idle"  # idle, running, completed, blocked, paused
    
    # Progress (0.0 - 1.0) for current phase
    progress: float = 0.0
    
    # Tasks
    current_task: str | None = None
    next_task: str | None = None
    completed_tasks: list[str] = []
    pending_tasks: list[str] = []
    
    # Blockers
    blockers: list[FlowBlocker] = []
    
    # Metrics
    metrics: FlowMetrics = Field(default_factory=FlowMetrics)
    
    # Activity feed
    activities: list[dict[str, Any]] = []
    
    # Timestamps
    phase_started_at: str | None = None
    updated_at: str = ""
    
    # Convenience
    opportunity_title: str | None = None
    match_score: float = 0.0
    deployed: bool = False


def write_state(
    cycle: int,
    phase: str,
    opportunity: dict[str, Any] | None = None,
    build_output: str | None = None,
    match_score: float = 0.0,
    deployed: bool = False,
) -> None:
    """Write the current flow state to disk."""
    state = {
        "cycle": cycle,
        "phase": phase,
        "opportunity": opportunity or None,
        "build_output": build_output or None,
        "match_score": match_score,
        "deployed": deployed,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    try:
        # Validate path before writing
        _safe_path(STATE_FILE)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Failed to write state: {e}")


def write_flow_breakdown(
    cycle: int,
    phase: str,
    sub_phase: str | None = None,
    status: str = "running",
    progress: float = 0.0,
    current_task: str | None = None,
    next_task: str | None = None,
    completed_tasks: list[str] | None = None,
    pending_tasks: list[str] | None = None,
    blockers: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
    activity: dict[str, Any] | None = None,
    opportunity_title: str | None = None,
    match_score: float = 0.0,
    deployed: bool = False,
) -> None:
    """
    Write granular flow breakdown state.
    
    Call this at every milestone for detailed dashboard tracking.
    Each call with `activity` adds to the activity feed.
    """
    BREAKDOWN_FILE = Path("/tmp/sentinel_v2_flow_breakdown.json")
    
    # Validate path before using
    try:
        _safe_path(BREAKDOWN_FILE)
    except ValueError as e:
        print(f"Path validation failed: {e}")
        return
    
    # Load existing or create new
    breakdown = {}
    if BREAKDOWN_FILE.exists():
        try:
            with open(BREAKDOWN_FILE, "r") as f:
                breakdown = json.load(f)
        except Exception:
            breakdown = {}
    
    # Build the breakdown
    now = datetime.now(timezone.utc).isoformat()
    
    # If phase changed, reset sub_phase tracking
    if breakdown.get("phase") != phase:
        breakdown["phase_started_at"] = now
        breakdown["sub_phase"] = None
        breakdown["completed_tasks"] = []
        breakdown["pending_tasks"] = []
        breakdown["blockers"] = []
    
    breakdown.update({
        "cycle": cycle,
        "phase": phase,
        "sub_phase": sub_phase,
        "status": status,
        "progress": progress,
        "current_task": current_task,
        "next_task": next_task,
        "completed_tasks": completed_tasks or breakdown.get("completed_tasks", []),
        "pending_tasks": pending_tasks or breakdown.get("pending_tasks", []),
        "blockers": blockers or breakdown.get("blockers", []),
        "metrics": metrics or breakdown.get("metrics", {}),
        "opportunity_title": opportunity_title or (breakdown.get("opportunity_title")),
        "match_score": match_score or breakdown.get("match_score", 0.0),
        "deployed": deployed,
        "updated_at": now,
    })
    
    # Add activity to feed (keep last 50)
    if activity:
        activities = breakdown.get("activities", [])
        activities.append({
            **activity,
            "timestamp": now,
        })
        activities = activities[-50:]
        breakdown["activities"] = activities
    
    try:
        with open(BREAKDOWN_FILE, "w") as f:
            json.dump(breakdown, f, indent=2)
    except Exception as e:
        print(f"Failed to write flow breakdown: {e}")


def add_blocker(
    blocker_id: str,
    description: str,
    severity: str = "medium",
) -> None:
    """Add a blocker to the current flow breakdown."""
    BREAKDOWN_FILE = Path("/tmp/sentinel_v2_flow_breakdown.json")
    
    # Validate path
    try:
        _safe_path(BREAKDOWN_FILE)
    except ValueError as e:
        print(f"Path validation failed: {e}")
        return
    
    if not BREAKDOWN_FILE.exists():
        return
    
    try:
        with open(BREAKDOWN_FILE, "r") as f:
            breakdown = json.load(f)
    except Exception:
        return
    
    blockers = breakdown.get("blockers", [])
    # Don't add duplicate
    for b in blockers:
        if b.get("id") == blocker_id:
            return
    
    blockers.append({
        "id": blocker_id,
        "description": description,
        "severity": severity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved": False,
    })
    breakdown["blockers"] = blockers
    
    with open(BREAKDOWN_FILE, "w") as f:
        json.dump(breakdown, f, indent=2)


def resolve_blocker(blocker_id: str) -> None:
    """Mark a blocker as resolved."""
    BREAKDOWN_FILE = Path("/tmp/sentinel_v2_flow_breakdown.json")
    
    # Validate path
    try:
        _safe_path(BREAKDOWN_FILE)
    except ValueError as e:
        print(f"Path validation failed: {e}")
        return
    
    if not BREAKDOWN_FILE.exists():
        return
    
    try:
        with open(BREAKDOWN_FILE, "r") as f:
            breakdown = json.load(f)
    except Exception:
        return
    
    for b in breakdown.get("blockers", []):
        if b.get("id") == blocker_id:
            b["resolved"] = True
    
    with open(BREAKDOWN_FILE, "w") as f:
        json.dump(breakdown, f, indent=2)


def add_agent_message(
    agent_id: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    cycle: int | None = None,
) -> None:
    """Add a message from an agent to the chat."""
    # Sanitize agent_id
    agent_id = _sanitize_agent_id(agent_id)
    
    # Validate agent messages file path
    try:
        _safe_path(AGENT_MESSAGES_FILE)
    except ValueError as e:
        print(f"Path validation failed: {e}")
        return
    
    messages = []
    
    # Load existing messages
    if AGENT_MESSAGES_FILE.exists():
        try:
            with open(AGENT_MESSAGES_FILE, "r") as f:
                messages = json.load(f)
        except Exception:
            messages = []
    
    # Add new message
    messages.append({
        "agent_id": agent_id,
        "message": message,
        "metadata": metadata or {},
        "cycle": cycle,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    
    # Keep only last 100 messages
    messages = messages[-100:]
    
    try:
        with open(AGENT_MESSAGES_FILE, "w") as f:
            json.dump(messages, f, indent=2)
    except Exception as e:
        print(f"Failed to write agent message: {e}")


def get_agent_messages() -> list[dict]:
    """Get all agent messages."""
    try:
        _safe_path(AGENT_MESSAGES_FILE)
    except ValueError:
        return []
    
    if not AGENT_MESSAGES_FILE.exists():
        return []
    try:
        with open(AGENT_MESSAGES_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def read_flow_breakdown() -> dict:
    """Read the current flow breakdown."""
    BREAKDOWN_FILE = Path("/tmp/sentinel_v2_flow_breakdown.json")
    
    try:
        _safe_path(BREAKDOWN_FILE)
    except ValueError:
        # Return empty default if path validation fails
        return {
            "cycle": 0,
            "phase": "idle",
            "sub_phase": None,
            "status": "idle",
            "progress": 0.0,
            "current_task": None,
            "next_task": None,
            "completed_tasks": [],
            "pending_tasks": [],
            "blockers": [],
            "metrics": {},
            "activities": [],
            "opportunity_title": None,
            "match_score": 0.0,
            "deployed": False,
            "updated_at": "",
        }
    
    if not BREAKDOWN_FILE.exists():
        return {
            "cycle": 0,
            "phase": "idle",
            "sub_phase": None,
            "status": "idle",
            "progress": 0.0,
            "current_task": None,
            "next_task": None,
            "completed_tasks": [],
            "pending_tasks": [],
            "blockers": [],
            "metrics": {},
            "activities": [],
            "opportunity_title": None,
            "match_score": 0.0,
            "deployed": False,
            "updated_at": "",
        }
    try:
        with open(BREAKDOWN_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# ── Drafts (unified pipeline model) ──────────────────────────────────────────


def _read_drafts_file() -> dict:
    """Low-level read of the drafts JSON file."""
    if not DRAFTS_FILE.exists():
        return {"drafts": [], "updated_at": ""}
    try:
        with open(DRAFTS_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("drafts"), list):
                return data
    except (IOError, json.JSONDecodeError):
        pass
    return {"drafts": [], "updated_at": ""}


def _write_drafts_file(data: dict) -> None:
    try:
        _safe_path(DRAFTS_FILE)
        with open(DRAFTS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:  # noqa: BLE001
        print(f"Failed to write drafts: {e}")


def write_draft(
    draft_id: str,
    cycle: int,
    title: str,
    *,
    tagline: str | None = None,
    description: str | None = None,
    problem: str | None = None,
    solution: str | None = None,
    tech_fit: float = 0.0,
    complexity: int = 0,
    estimated_hours: int | None = None,
    tags: list[str] | None = None,
    status: str = "pending",
) -> None:
    """Create or upsert a draft entry for the unified dashboard pipeline.

    Called during the research/match phase when Sentinel surfaces an opportunity.
    Subsequent phases should use :func:`update_draft` to flip status / progress.
    """
    data = _read_drafts_file()
    drafts: list[dict] = data.get("drafts", [])
    now = datetime.now(timezone.utc).isoformat()
    found = False
    for d in drafts:
        if d.get("id") == draft_id:
            d.update(
                {
                    "cycle": cycle,
                    "title": title,
                    "tagline": tagline or d.get("tagline", ""),
                    "description": description or d.get("description", ""),
                    "problem": problem or d.get("problem", ""),
                    "solution": solution or d.get("solution", ""),
                    "tech_fit": float(tech_fit),
                    "complexity": int(complexity),
                    "estimated_hours": estimated_hours,
                    "tags": tags or d.get("tags", []),
                    "status": status,
                    "updated_at": now,
                }
            )
            found = True
            break
    if not found:
        drafts.append(
            {
                "id": draft_id,
                "cycle": cycle,
                "title": title,
                "tagline": tagline or "",
                "description": description or "",
                "problem": problem or "",
                "solution": solution or "",
                "tech_fit": float(tech_fit),
                "complexity": int(complexity),
                "estimated_hours": estimated_hours,
                "tags": tags or [],
                "status": status,
                "created_at": now,
                "updated_at": now,
                "build_progress": 0.0,
            }
        )
    data["drafts"] = drafts
    data["updated_at"] = now
    _write_drafts_file(data)


def update_draft(draft_id: str, **fields: Any) -> bool:
    """Patch arbitrary fields on a single draft (status, build_progress, metrics, etc.)."""
    data = _read_drafts_file()
    drafts: list[dict] = data.get("drafts", [])
    now = datetime.now(timezone.utc).isoformat()
    for d in drafts:
        if d.get("id") == draft_id:
            d.update(fields)
            d["updated_at"] = now
            data["drafts"] = drafts
            data["updated_at"] = now
            _write_drafts_file(data)
            return True
    return False


def get_draft(draft_id: str) -> dict | None:
    data = _read_drafts_file()
    for d in data.get("drafts", []):
        if d.get("id") == draft_id:
            return d
    return None


def wait_for_draft_status(
    draft_id: str,
    target_statuses: set[str],
    *,
    poll_interval: float = 2.0,
    timeout_seconds: float = 3600.0,
) -> str | None:
    """Block until a draft reaches one of the target statuses or timeout.

    Returns the matching status, or ``None`` on timeout.
    """
    import time

    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        draft = get_draft(draft_id)
        if draft and draft.get("status") in target_statuses:
            return draft["status"]
        time.sleep(poll_interval)
    return None


def make_draft_id(cycle: int, opportunity: dict | None) -> str:
    """Deterministic id from cycle + opportunity title so upserts work."""
    title = (opportunity or {}).get("title") or "opportunity"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "draft"
    return f"draft_c{cycle}_{slug}"
