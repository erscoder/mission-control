"""
Telegram bot handler for claude-session.
Handles /sessions command and inline button callbacks.

Commands:
  python3 telegram_bot.py list                            → session list as text
  python3 telegram_bot.py buttons                         → session list as JSON for message tool
  python3 telegram_bot.py events <sid>                    → recent events text
  python3 telegram_bot.py watch <sid>                     → start watching, returns JSON
  python3 telegram_bot.py poll                           → poll all watches, returns JSON updates
  python3 telegram_bot.py stop <sid>                     → stop watching
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Paths
SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "watch_state.json"
SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"


# ------------------------------------------------------------------
# State management
# ------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"watches": {}}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ------------------------------------------------------------------
# Session discovery
# ------------------------------------------------------------------

def list_sessions() -> list[dict]:
    sessions = []
    if not SESSIONS_DIR.exists():
        return sessions
    for entry in SESSIONS_DIR.iterdir():
        if entry.suffix != ".json":
            continue
        try:
            with open(entry) as f:
                sessions.append(json.load(f))
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    sessions.sort(key=lambda s: s.get("startedAt", 0), reverse=True)
    return sessions


def resolve_session_id(session_id: str) -> str | None:
    if len(session_id) == 36:
        return session_id
    sessions = list_sessions()
    for s in sessions:
        if s.get("sessionId", "").startswith(session_id):
            return s["sessionId"]
    for s in sessions:
        name = s.get("name", "").lower()
        if session_id.lower() in name or name.startswith(session_id.lower()):
            return s["sessionId"]
    for s in sessions:
        if str(s.get("pid", "")) == session_id:
            return s["sessionId"]
    return None


def get_session_path(session_id: str) -> Path | None:
    if not PROJECTS_DIR.exists():
        return None
    for entry in PROJECTS_DIR.iterdir():
        if not entry.is_dir():
            continue
        p = entry / f"{session_id}.jsonl"
        if p.exists():
            return p
        for sub in entry.iterdir():
            if not sub.is_dir():
                continue
            if sub.name == session_id:
                p2 = sub / f"{session_id}.jsonl"
                if p2.exists():
                    return p2
            elif sub.name == "subagents":
                for sf in sub.iterdir():
                    if sf.name.endswith(".jsonl") and sf.name.startswith(session_id):
                        return sf
    return None


# ------------------------------------------------------------------
# Text extraction from JSONL
# ------------------------------------------------------------------

def extract_user_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    parts = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                txt = block.get("text", "")
                if txt:
                    parts.append(txt)
    return " ".join(parts)


def get_recent_events_text(session_id: str, limit: int = 20) -> str:
    resolved = resolve_session_id(session_id)
    if not resolved:
        return f"Session not found: {session_id}"
    jl_path = get_session_path(resolved)
    if not jl_path or not jl_path.exists():
        return f"Session file not found for {resolved[:8]}"

    with open(jl_path) as f:
        lines = f.readlines()

    recent = lines[-limit:] if len(lines) > limit else lines
    events = []
    for line in recent:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    if not events:
        return "No events found."

    parts = []
    for ev in events:
        evtype = ev.get("type", "")

        if evtype == "user":
            msg = ev.get("message", {})
            content = msg.get("content", [])
            text = extract_user_text(content)
            if text:
                parts.append(f"👤 {text[:200]}")
            continue

        if evtype == "assistant":
            msg = ev.get("message", {})
            content = msg.get("content", [])
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    txt = block.get("text", "")
                    if txt.strip():
                        parts.append(f"🤖 {txt[:200]}")
                elif btype == "tool_use":
                    name = block.get("name", "unknown")
                    inp = block.get("input", {})
                    if name == "Bash":
                        cmd = inp.get("command", "")
                        parts.append(f"⚡ {cmd[:100]}")
                    elif name == "Write":
                        path = inp.get("file_path", "?")
                        parts.append(f"✏️ Write `{path}`")
                    elif name == "Edit":
                        path = inp.get("file_path", "?")
                        parts.append(f"📝 Edit `{path}`")
                    elif name == "Read":
                        path = inp.get("file_path", "?")
                        parts.append(f"📄 Read `{path}`")
                    elif name == "TodoWrite":
                        todos = inp.get("todos", [])
                        done = sum(1 for t in todos if t.get("status") == "completed")
                        parts.append(f"📋 Tasks: {done}/{len(todos)}")
                    elif name == "Glob":
                        pat = inp.get("pattern", "*")
                        parts.append(f"🔍 Glob `{pat}`")
                    elif name == "Grep":
                        q = inp.get("query", "")
                        parts.append(f"🔍 Grep `{q[:60]}`")
                    elif name == "WebFetch":
                        url = inp.get("url", "")[:60]
                        parts.append(f"🌐 Fetch `{url}`")
                    elif name == "WebSearch":
                        q = inp.get("query", "")
                        parts.append(f"🔎 Search `{q[:60]}`")
                    else:
                        parts.append(f"🔧 {name}")
            continue

    if not parts:
        return "No text events yet."

    return "\n".join(parts[-10:])


def get_line_count(session_id: str) -> int:
    resolved = resolve_session_id(session_id)
    if not resolved:
        return 0
    jl_path = get_session_path(resolved)
    if not jl_path or not jl_path.exists():
        return 0
    with open(jl_path) as f:
        return sum(1 for _ in f)


# ------------------------------------------------------------------
# List + buttons for Telegram
# ------------------------------------------------------------------

def format_sessions_for_telegram() -> dict:
    """Returns dict with text and inline_keyboard for message tool."""
    sessions = list_sessions()
    if not sessions:
        return {"text": "No sessions found.", "buttons": []}

    lines = ["*Claude Code Sessions*\nSelect one to see recent activity:\n"]

    keyboard_rows = []
    for i, s in enumerate(sessions):
        sid = s.get("sessionId", "-")
        name = s.get("name", "-") or "—"
        short_sid = sid[:8]
        project = s.get("cwd", s.get("project", "-"))
        if project.startswith("/Users/kike/"):
            project = "~" + project[len("/Users/kike/"):]
        started_ms = s.get("startedAt", 0)
        if started_ms:
            dt = datetime.fromtimestamp(started_ms / 1000)
            started = dt.strftime("%m-%d %H:%M")
        else:
            started = "—"

        lines.append(f"*{name}*  `{short_sid}`")
        lines.append(f"   📁 {project}  🕐 {started}\n")

        keyboard_rows.append({
            "text": f"▶ {name} ({short_sid})",
            "callback_data": f"cs:events:{sid}",
        })

    text = "\n".join(lines)

    # Group buttons in rows of 2
    keyboard = []
    row = []
    for btn in keyboard_rows:
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    return {"text": text, "buttons": keyboard}


def format_events_for_telegram(session_id: str) -> dict:
    """Returns dict with text and inline_keyboard for message tool."""
    resolved = resolve_session_id(session_id)
    if not resolved:
        return {"text": f"Session not found: {session_id}", "buttons": []}

    name = None
    for s in list_sessions():
        if s.get("sessionId") == resolved:
            name = s.get("name", "") or resolved[:8]
            break
    if not name:
        name = resolved[:8]

    text = get_recent_events_text(resolved)
    current_count = get_line_count(resolved)

    keyboard = [
        [
            {"text": "🔄 Refresh", "callback_data": f"cs:events:{resolved}"},
            {"text": "👁 Watch", "callback_data": f"cs:watch:{resolved}:{current_count}"},
        ],
        [
            {"text": "🔙 Back to list", "callback_data": "cs:list"},
        ],
    ]

    return {"text": text, "buttons": keyboard, "sid": resolved, "name": name}


def format_watch_for_telegram(session_id: str, last_count: int) -> dict:
    """Start watching, return current events and updated line count."""
    resolved = resolve_session_id(session_id)
    if not resolved:
        return {"text": f"Session not found: {session_id}", "buttons": []}

    name = None
    for s in list_sessions():
        if s.get("sessionId") == resolved:
            name = s.get("name", "") or resolved[:8]
            break
    if not name:
        name = resolved[:8]

    # Save watch state
    state = load_state()
    state["watches"][f"{resolved[:8]}"] = {
        "full_sid": resolved,
        "last_count": last_count,
        "chat_id": None,  # Will be filled by caller
        "started_at": datetime.now().isoformat(),
    }
    save_state(state)

    text = get_recent_events_text(resolved, limit=15)
    current_count = get_line_count(resolved)

    keyboard = [
        [
            {"text": "🔄 Refresh", "callback_data": f"cs:events:{resolved}"},
            {"text": "⏹ Stop", "callback_data": f"cs:stop:{resolved}"},
        ],
        [
            {"text": "🔙 Back to list", "callback_data": "cs:list"},
        ],
    ]

    return {
        "text": f"👁 *Watching:* `{name}`\n\n{text}",
        "buttons": keyboard,
        "sid": resolved,
        "name": name,
        "last_count": current_count,
        "watching": True,
    }


def poll_watches() -> list[dict]:
    """Poll all active watches, return list of updates."""
    state = load_state()
    updates = []

    for short_sid, watch in list(state["watches"].items()):
        full_sid = watch["full_sid"]
        last_count = watch["last_count"]
        jl_path = get_session_path(full_sid)

        if not jl_path or not jl_path.exists():
            updates.append({
                "sid": short_sid,
                "name": watch.get("name", short_sid),
                "text": f"Session {short_sid} ended.",
                "stop": True,
            })
            continue

        current_count = sum(1 for _ in open(jl_path))
        if current_count > last_count:
            # New events
            with open(jl_path) as f:
                lines = f.readlines()
            new_lines = lines[last_count:]
            new_events = []
            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    new_events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

            parts = []
            for ev in new_events:
                evtype = ev.get("type", "")
                if evtype == "user":
                    msg = ev.get("message", {})
                    content = msg.get("content", [])
                    text = extract_user_text(content)
                    if text:
                        parts.append(f"👤 {text[:150]}")
                elif evtype == "assistant":
                    msg = ev.get("message", {})
                    content = msg.get("content", [])
                    for block in content if isinstance(content, list) else []:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "text":
                            txt = block.get("text", "")
                            if txt.strip():
                                parts.append(f"🤖 {txt[:150]}")
                        elif btype == "tool_use":
                            name = block.get("name", "unknown")
                            inp = block.get("input", {})
                            if name == "Bash":
                                cmd = inp.get("command", "")
                                parts.append(f"⚡ {cmd[:80]}")
                            elif name == "Write":
                                path = inp.get("file_path", "?")
                                parts.append(f"✏️ Write `{path}`")
                            elif name == "Edit":
                                path = inp.get("file_path", "?")
                                parts.append(f"📝 Edit `{path}`")
                            elif name == "TodoWrite":
                                todos = inp.get("todos", [])
                                done = sum(1 for t in todos if t.get("status") == "completed")
                                parts.append(f"📋 Tasks: {done}/{len(todos)}")
                            else:
                                parts.append(f"🔧 {name}")

            if parts:
                # Update state
                state["watches"][short_sid]["last_count"] = current_count
                save_state(state)

                updates.append({
                    "sid": short_sid,
                    "name": watch.get("name", short_sid),
                    "text": f"*New in `{watch.get('name', short_sid)}`*\n" + "\n".join(parts[-5:]),
                    "last_count": current_count,
                })

    return updates


def stop_watch(session_id: str) -> bool:
    resolved = resolve_session_id(session_id)
    if not resolved:
        return False
    short_sid = resolved[:8]
    state = load_state()
    if short_sid in state["watches"]:
        del state["watches"][short_sid]
        save_state(state)
        return True
    return False


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    arg1 = sys.argv[2] if len(sys.argv) > 2 else ""
    arg2 = sys.argv[3] if len(sys.argv) > 3 else ""

    if cmd == "list":
        result = format_sessions_for_telegram()
        print(json.dumps(result))

    elif cmd == "events":
        result = format_events_for_telegram(arg1)
        print(json.dumps(result))

    elif cmd == "watch":
        last_count = int(arg2) if arg2 else 0
        result = format_watch_for_telegram(arg1, last_count)
        print(json.dumps(result))

    elif cmd == "poll":
        updates = poll_watches()
        print(json.dumps({"updates": updates}))

    elif cmd == "stop":
        stopped = stop_watch(arg1)
        print(json.dumps({"stopped": stopped}))

    elif cmd == "state":
        print(json.dumps(load_state(), indent=2))
