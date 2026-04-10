"""
Parser for Claude Code session JSONL files.
Each line is a JSON event with a 'type' field.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserMessage:
    content: str | list[dict]
    timestamp: str
    cwd: str
    session_id: str


@dataclass
class ToolCall:
    name: str
    input_data: dict
    id: str = ""


@dataclass
class ToolResult:
    tool_use_id: str
    content: str | list


@dataclass
class AssistantMessage:
    thinking: str | None = None
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str | None = None


@dataclass
class Attachment:
    attachment_type: str
    data: Any


@dataclass
class SessionEvent:
    """Union type for all session events."""
    event_type: str
    data: Any

    @property
    def is_user(self) -> bool:
        return self.event_type == "user"

    @property
    def is_assistant(self) -> bool:
        return self.event_type == "assistant"

    @property
    def is_attachment(self) -> bool:
        return self.event_type == "attachment"

    @property
    def is_queue_operation(self) -> bool:
        return self.event_type == "queue-operation"


def parse_message_content(content: Any) -> tuple[str | None, list[ToolCall], str | None]:
    """Parse assistant message content into thinking, text, and tool_calls."""
    thinking = None
    text_parts = []
    tool_calls = []

    if not isinstance(content, list):
        text_parts.append(str(content))
        return None, "".join(text_parts), tool_calls

    for block in content:
        if not isinstance(block, dict):
            text_parts.append(str(block))
            continue

        btype = block.get("type", "")

        if btype == "thinking":
            thinking = block.get("thinking", "")
        elif btype == "text":
            txt = block.get("text", "")
            if txt:
                text_parts.append(txt)
        elif btype == "tool_use":
            tool_calls.append(ToolCall(
                name=block.get("name", "unknown"),
                input_data=block.get("input", {}),
                id=block.get("id", ""),
            ))
        elif btype == "redacted_reason":
            text_parts.append(f"[redacted: {block.get('redacted_reason', 'unknown')}]")

    return thinking, "".join(text_parts) if text_parts else None, tool_calls


def parse_user_content(content: Any) -> str:
    """Extract user message text from content."""
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return str(content)

    parts = []
    for block in content:
        if not isinstance(block, dict):
            parts.append(str(block))
            continue

        btype = block.get("type", "")

        if btype == "text":
            txt = block.get("text", "")
            if txt:
                parts.append(txt)
        elif btype == "tool_result":
            # tool results can be shown differently
            tool_id = block.get("tool_use_id", "")[:16]
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                for item in result_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(f"[{tool_id}] {item.get('text', '')}")
            elif isinstance(result_content, str):
                parts.append(f"[{tool_id}] {result_content}")
        elif btype == "tool_use":
            tool_name = block.get("name", "unknown")
            parts.append(f"[tool: {tool_name}]")

    return "\n".join(parts)


def parse_tool_result_content(content: Any) -> str:
    """Extract readable content from tool result."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "resource":
                    parts.append(f"[resource: {item.get('uri', '')}]")
                elif item.get("type") == "tool_reference":
                    parts.append(f"[ref: {item.get('tool_name', '')}]")
        return "\n".join(parts)
    return str(content)


def parse_assistant_message(obj: dict) -> AssistantMessage:
    """Parse an assistant event into an AssistantMessage."""
    msg = obj.get("message", {})
    content = msg.get("content", [])
    thinking, text, tool_calls = parse_message_content(content)

    return AssistantMessage(
        thinking=thinking,
        text=text,
        tool_calls=tool_calls,
        model=msg.get("model"),
    )


def parse_user_event(obj: dict) -> UserMessage:
    """Parse a user event into a UserMessage."""
    msg = obj.get("message", {})
    return UserMessage(
        content=parse_user_content(msg.get("content", "")),
        timestamp=obj.get("timestamp", ""),
        cwd=obj.get("cwd", ""),
        session_id=obj.get("sessionId", ""),
    )


def parse_attachment(obj: dict) -> Attachment:
    """Parse an attachment event."""
    att = obj.get("attachment", {})
    return Attachment(
        attachment_type=att.get("type", "unknown"),
        data=att,
    )


def parse_event(line: str) -> SessionEvent | None:
    """Parse a single JSONL line into a SessionEvent."""
    try:
        obj = json.loads(line.strip())
    except (json.JSONDecodeError, TypeError):
        return None

    event_type = obj.get("type", "")
    return SessionEvent(event_type=event_type, data=obj)


def parse_session_metadata(session_file_path: str) -> dict:
    """Parse a session metadata JSON file."""
    try:
        with open(session_file_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        return {}


def find_session_jsonl(session_id: str, projects_dir: str = None) -> str | None:
    """Find the JSONL file for a given session ID."""
    import os

    if projects_dir is None:
        projects_dir = os.path.expanduser("~/.claude/projects")

    if not os.path.exists(projects_dir):
        return None

    for entry in os.scandir(projects_dir):
        if not entry.is_dir():
            continue
        jl_path = os.path.join(entry.path, f"{session_id}.jsonl")
        if os.path.exists(jl_path):
            return jl_path

    return None
