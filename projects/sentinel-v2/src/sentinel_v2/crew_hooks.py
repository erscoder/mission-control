"""CrewAI Crew hooks for streaming agent messages to dashboard.

This module adds callbacks to CrewAI agents/tasks to emit messages
to /tmp/sentinel_v2_agent_messages.json in real-time.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Callable, Any
from crewai import Agent, Task, Crew, LLM
from enum import Enum

_TMP_DIR = Path(os.environ.get("SENTINEL_TMPDIR", "/tmp"))

# File to store agent messages
AGENT_MESSAGES_FILE = _TMP_DIR / "sentinel_v2_agent_messages.json"
# Lock for thread-safe file writing
_messages_lock = threading.Lock()
log = logging.getLogger("sentinel_v2.crew_hooks")


class AgentHookType(Enum):
    """Types of agent lifecycle hooks."""
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    AGENT_THOUGHT = "agent_thought"
    AGENT_ACTION = "agent_action"
    AGENT_OUTPUT = "agent_output"
    TOOL_EXECUTION = "tool_execution"


# ── Path Validation ──────────────────────────────────────────────────────────

ALLOWED_TMP_PREFIX = str(_TMP_DIR) + "/sentinel_v2_"


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

    Spaces collapse to dashes; only lowercase alphanumerics and dashes survive;
    any other character (including underscore, dot, slash, colon) is removed.
    """
    sanitized = agent_id.lower().replace(" ", "-")
    sanitized = re.sub(r"[^a-z0-9\-]", "", sanitized)
    sanitized = re.sub(r"-+", "-", sanitized)
    sanitized = sanitized.strip("-")
    return sanitized or "unknown"


def add_agent_message(
    agent_id: str,
    message: str,
    hook_type: str = AgentHookType.AGENT_OUTPUT.value,
    phase: str | None = None,
    cycle: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Thread-safe agent message writer to shared file.
    
    Args:
        agent_id: Agent identifier (e.g., 'web-scout', 'code-reviewer')
        message: The text output from the agent
        hook_type: Type of event (task_started, task_completed, agent_output, etc.)
        phase: Current workflow phase (research, match, build, approve, deploy)
        cycle: Cycle number
        metadata: Additional data (files reviewed, issues found, etc.)
    """
    # Sanitize agent_id before any use in paths/logs
    agent_id = _sanitize_agent_id(agent_id)
    
    msg_data = {
        "agent_id": agent_id,
        "message": message,
        "hook_type": hook_type,
        "phase": phase or "unknown",
        "metadata": metadata or {},
        "cycle": cycle or 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    with _messages_lock:
        existing_messages = []
        try:
            if AGENT_MESSAGES_FILE.exists() and AGENT_MESSAGES_FILE.stat().st_size > 0:
                with open(AGENT_MESSAGES_FILE, "r") as f:
                    existing_messages = json.load(f)
        except (IOError, json.JSONDecodeError, ValueError):
            existing_messages = []

        existing_messages.append(msg_data)

        # Keep only last 500 messages
        if len(existing_messages) > 500:
            existing_messages = existing_messages[-500:]

        try:
            _safe_path(AGENT_MESSAGES_FILE)
            with open(AGENT_MESSAGES_FILE, "w") as f:
                json.dump(existing_messages, f, indent=2)
        except (IOError, json.JSONDecodeError, ValueError) as exc:
            log.warning("Could not write agent messages file: %s", exc)


def _make_task_callback(phase: str, cycle: int) -> Callable:
    """Return a task_callback compatible with CrewAI Crew.task_callback.

    Fires after each task with a TaskOutput object that contains the actual
    agent result (.raw), the agent role (.agent), and the task description.
    """
    def _on_task_done(task_output: Any) -> None:
        agent_role = getattr(task_output, "agent", None) or "orchestrator"
        agent_id = _sanitize_agent_id(str(agent_role))
        raw = getattr(task_output, "raw", "") or ""
        summary = raw[:400].strip() if raw else "Task completed"
        add_agent_message(
            agent_id=agent_id,
            message=summary,
            hook_type=AgentHookType.TASK_COMPLETED.value,
            phase=phase,
            cycle=cycle,
            metadata={"preview": raw[:200]},
        )
    return _on_task_done


def crew_with_hooks(
    crew: Crew,
    phase: str = "unknown",
    cycle: int = 1
) -> Crew:
    """Add streaming hooks to a Crew instance.

    Attaches lifecycle callbacks to capture agent outputs and emit to dashboard.

    Args:
        crew: CrewAI Crew instance
        phase: Workflow phase this crew belongs to
        cycle: Cycle number

    Returns:
        Crew with hooks attached
    """
    # Wire task_callback so every completed task emits its real output
    crew.task_callback = _make_task_callback(phase, cycle)

    # Store original kickoff
    original_kickoff = crew.kickoff

    @wraps(original_kickoff)
    def kickoff_with_hooks(**kwargs) -> Any:
        """Enhanced kickoff that streams agent messages."""
        # Log phase start
        add_agent_message(
            agent_id="orchestrator",
            message=f"Starting phase: {phase}",
            hook_type="phase_started",
            phase=phase,
            cycle=cycle,
            metadata={"task_count": len(crew.tasks)}
        )

        # Hook into each task's lifecycle
        for task in crew.tasks:
            _hook_task(task, phase, cycle)

        # Log each agent
        for agent in crew.agents:
            add_agent_message(
                agent_id=_agent_id_from_agent(agent),
                message=f"Agent initialized: {agent.role}",
                hook_type="agent_initialized",
                phase=phase,
                cycle=cycle,
                metadata={
                    "role": agent.role,
                    "goal": agent.goal[:100] + "..." if len(agent.goal) > 100 else agent.goal
                }
            )

        # Run original kickoff
        try:
            result = original_kickoff(**kwargs)

            # Emit phase summary with the crew's actual output
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)
            add_agent_message(
                agent_id="orchestrator",
                message=raw_output[:500],
                hook_type="phase_completed",
                phase=phase,
                cycle=cycle,
                metadata={"status": "success", "result_preview": raw_output[:300]},
            )

            return result

        except Exception as e:
            # Log error
            add_agent_message(
                agent_id="orchestrator",
                message=f"Phase failed: {phase} - {str(e)}",
                hook_type="phase_error",
                phase=phase,
                cycle=cycle,
                metadata={"error": str(e)}
            )
            raise

    object.__setattr__(crew, 'kickoff', kickoff_with_hooks)
    return crew


def _hook_task(task: Task, phase: str, cycle: int) -> None:
    """Hook into task lifecycle to capture outputs."""
    task_json = {
        "id": str(id(task)),
        "description": task.description[:150] + "..." if len(task.description) > 150 else task.description,
        "expected_output": task.expected_output[:100] + "..." if len(task.expected_output) > 100 else task.expected_output,
    }
    
    add_agent_message(
        agent_id=_agent_id_from_task(task),
        message=f"Task started: {task.description[:80]}",
        hook_type=AgentHookType.TASK_STARTED.value,
        phase=phase,
        cycle=cycle,
        metadata={"task": task_json}
    )


def hook_agent_thought(
    agent_id: str,
    thought: str,
    phase: str,
    cycle: int
) -> None:
    """Hook agent thought (reasoning) output."""
    add_agent_message(
        agent_id=agent_id,
        message=f"Thinking: {thought[:200]}",
        hook_type=AgentHookType.AGENT_THOUGHT.value,
        phase=phase,
        cycle=cycle
    )


def hook_agent_action(
    agent_id: str,
    action: str,
    phase: str,
    cycle: int
) -> None:
    """Hook agent action output."""
    add_agent_message(
        agent_id=agent_id,
        message=f"Action: {action[:200]}",
        hook_type=AgentHookType.AGENT_ACTION.value,
        phase=phase,
        cycle=cycle
    )


def hook_agent_output(
    agent_id: str,
    output: str,
    phase: str,
    cycle: int,
    metadata: dict[str, Any] | None = None
) -> None:
    """Hook final agent output."""
    add_agent_message(
        agent_id=agent_id,
        message=output[:500],
        hook_type=AgentHookType.AGENT_OUTPUT.value,
        phase=phase,
        cycle=cycle,
        metadata=metadata or {}
    )


def hook_task_completed(
    task: Task,
    agent_id: str,
    result: str | None,
    phase: str,
    cycle: int
) -> None:
    """Hook task completion."""
    add_agent_message(
        agent_id=agent_id,
        message=f"Task completed: {task.description[:80]}",
        hook_type=AgentHookType.TASK_COMPLETED.value,
        phase=phase,
        cycle=cycle,
        metadata={
            "task_id": str(id(task)),
            "result_preview": result[:200] if result else "No output"
        }
    )


def _agent_id_from_agent(agent: Agent) -> str:
    """Extract standardized agent_id from Agent instance."""
    role = agent.role.lower()
    role_id_map = {
        "web scout": "web-scout",
        "analyst": "analyst",
        "profile researcher": "profile-researcher",
        "matcher": "matcher",
        "strategic product manager": "manager",
        "frontend lead": "frontend-dev",
        "backend lead": "backend-dev",
        "senior code reviewer": "code-reviewer",
        "security engineer": "security-auditor",
        "qa engineering lead": "qa-verifier",
        "deployment engineer": "deployer",
    }
    return role_id_map.get(role, role.replace(" ", "-"))


def _agent_id_from_task(task: Task) -> str:
    """Extract agent_id from task by matching agent."""
    if hasattr(task, 'agent') and task.agent:
        return _agent_id_from_agent(task.agent)
    return "orchestrator"


def hook_crew_full(
    crew: Crew,
    phase: str,
    cycle: int
) -> Crew:
    """Apply full instrumentation to a crew."""
    crew = crew_with_hooks(crew, phase=phase, cycle=cycle)
    return crew
