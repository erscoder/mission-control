"""Dashboard state manager for Sentinel V2.

Tracks flow state and agent messages for the real-time dashboard.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


STATE_FILE = Path("/tmp/sentinel_v2_state.json")
AGENT_MESSAGES_FILE = Path("/tmp/sentinel_v2_agent_messages.json")


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