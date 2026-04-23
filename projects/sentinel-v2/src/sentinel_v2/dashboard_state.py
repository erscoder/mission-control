"""
Dashboard state manager for Sentinel V2.

Tracks flow state and agent messages for the real-time dashboard.
Now includes granular FlowBreakdown for detailed phase tracking.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


STATE_FILE = Path("/tmp/sentinel_v2_state.json")
AGENT_MESSAGES_FILE = Path("/tmp/sentinel_v2_agent_messages.json")

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
