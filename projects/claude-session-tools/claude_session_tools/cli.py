"""
claude-session CLI tool.
Usage:
    claude-session list              List all sessions
    claude-session watch <id>        Watch a session live
    claude-session cat <id>          Print full session history
    claude-session tail <id>         Tail new events as they arrive
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .parser import (
    find_session_jsonl,
    parse_assistant_message,
    parse_event,
    parse_user_event,
)
from .renderer import SessionRenderer, ts


SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
console = Console()


def list_sessions() -> list[dict]:
    """List all sessions from ~/.claude/sessions/*.json."""
    sessions = []

    if not SESSIONS_DIR.exists():
        return sessions

    for entry in SESSIONS_DIR.iterdir():
        if entry.suffix != ".json":
            continue
        try:
            with open(entry) as f:
                data = json.load(f)
            sessions.append(data)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Sort by startedAt descending
    sessions.sort(key=lambda s: s.get("startedAt", 0), reverse=True)
    return sessions


def resolve_session_id(session_id: str) -> str | None:
    """Resolve a session ID (partial UUID or name)."""
    sessions = list_sessions()

    # Exact match
    for s in sessions:
        if s.get("sessionId", "").startswith(session_id):
            return s["sessionId"]

    # Name match
    for s in sessions:
        name = s.get("name", "").lower()
        if session_id.lower() in name or name.startswith(session_id.lower()):
            return s["sessionId"]

    # PID match
    for s in sessions:
        if str(s.get("pid", "")) == session_id:
            return s["sessionId"]

    return session_id if len(session_id) == 36 else None


def get_session_path(session_id: str) -> Path | None:
    """Get the JSONL path for a session ID."""
    if not PROJECTS_DIR.exists():
        return None

    for entry in PROJECTS_DIR.iterdir():
        if not entry.is_dir():
            continue
        jl_path = entry / f"{session_id}.jsonl"
        if jl_path.exists():
            return jl_path

    return None


def read_session_events(session_id: str, limit: int | None = None) -> list:
    """Read all events from a session's JSONL file."""
    jl_path = get_session_path(session_id)
    if not jl_path:
        # Try finding by partial ID
        for entry in PROJECTS_DIR.iterdir():
            if not entry.is_dir():
                continue
            for f in entry.iterdir():
                if f.name.endswith(".jsonl") and f.name.startswith(session_id):
                    jl_path = f
                    break
            if jl_path:
                break

    if not jl_path or not jl_path.exists():
        return []

    events = []
    with open(jl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = parse_event(line)
            if ev:
                events.append(ev)
            if limit and len(events) >= limit:
                break

    return events


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

@click.group()
@click.version_option(version="0.1.0")
def main():
    """claude-session — Proxy viewer for Claude Code CLI sessions."""
    pass


@main.command('list')
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all fields")
def list_cmd(show_all: bool):
    """List all Claude Code sessions."""
    sessions = list_sessions()

    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    table = Table(title="Claude Code Sessions", show_header=True)
    table.add_column("PID", style="cyan", width=6)
    table.add_column("Session ID", style="dim", width=36)
    table.add_column("Project", style="blue")
    table.add_column("Name", style="green")
    table.add_column("Started", style="yellow")

    for s in sessions:
        pid = str(s.get("pid", "-"))
        sid = s.get("sessionId", "-")
        name = s.get("name", "-")
        project = s.get("cwd", s.get("project", "-"))
        # Shorten project path
        if project.startswith("/Users/kike/"):
            project = "~" + project[len("/Users/kike/"):]
        started_ms = s.get("startedAt", 0)
        if started_ms:
            import datetime
            dt = datetime.datetime.fromtimestamp(started_ms / 1000)
            started = dt.strftime("%m-%d %H:%M")
        else:
            started = "-"

        table.add_row(pid, sid[:36], project, name or "-", started)

    console.print(table)
    console.print(f"\n[dim]{len(sessions)} sessions total.[/dim]")
    console.print(f"\n[dim]Use: claude-session cat <session-id>  to view a session[/dim]")
    console.print(f"[dim]Use: claude-session watch <session-id>  to watch live[/dim]")


@main.command()
@click.argument("session_id")
@click.option("--limit", "-n", default=200, help="Number of events to show")
def cat(session_id: str, limit: int):
    """Print the full history of a session with rendered output."""
    resolved = resolve_session_id(session_id)
    if not resolved:
        console.print(f"[red]Session not found: {session_id}[/red]")
        sys.exit(1)

    events = read_session_events(resolved, limit=limit)
    if not events:
        console.print(f"[yellow]No events found for session {resolved}[/yellow]")
        sys.exit(1)

    renderer = SessionRenderer(console)
    renderer.render_session_events(events, limit=limit)


@main.command()
@click.argument("session_id")
def watch(session_id: str):
    """Watch a session live (tail + render new events)."""
    import time
    from watchfiles import watch

    resolved = resolve_session_id(session_id)
    if not resolved:
        console.print(f"[red]Session not found: {session_id}[/red]")
        sys.exit(1)

    jl_path = get_session_path(resolved)
    if not jl_path:
        # Search in project dirs
        for entry in PROJECTS_DIR.iterdir():
            if not entry.is_dir():
                continue
            p = entry / f"{resolved}.jsonl"
            if p.exists():
                jl_path = p
                break

    if not jl_path or not jl_path.exists():
        console.print(f"[red]Session file not found for {resolved}[/red]")
        sys.exit(1)

    console.print(f"[green]Watching session[/green] {resolved}")
    console.print(f"[dim]File: {jl_path}[/dim]")
    console.print(f"[dim]Press Ctrl+C to stop.[/dim]\n")

    # First, show recent events
    events = read_session_events(resolved, limit=50)
    renderer = SessionRenderer(console)
    renderer.render_session_events(events)

    # Track line count for tail
    last_line_count = sum(1 for _ in open(jl_path))

    for changes in watch(jl_path, poll_delay_seconds=1):
        current_line_count = sum(1 for _ in open(jl_path))
        if current_line_count > last_line_count:
            # New events appended
            with open(jl_path) as f:
                lines = f.readlines()

            new_lines = lines[last_line_count:]
            new_events = []
            for line in new_lines:
                ev = parse_event(line)
                if ev:
                    new_events.append(ev)

            if new_events:
                renderer.render_session_events(new_events)

            last_line_count = current_line_count


@main.command()
@click.argument("session_id")
def tail(session_id: str):
    """Tail new events only (no history)."""
    import time
    from watchfiles import watch

    resolved = resolve_session_id(session_id)
    if not resolved:
        console.print(f"[red]Session not found: {session_id}[/red]")
        sys.exit(1)

    jl_path = get_session_path(resolved)
    if not jl_path:
        for entry in PROJECTS_DIR.iterdir():
            if not entry.is_dir():
                continue
            p = entry / f"{resolved}.jsonl"
            if p.exists():
                jl_path = p
                break

    if not jl_path or not jl_path.exists():
        console.print(f"[red]Session file not found[/red]")
        sys.exit(1)

    renderer = SessionRenderer(console)
    last_line_count = sum(1 for _ in open(jl_path))

    console.print(f"[green]Tailing session[/green] {resolved} (new events only)\n")

    for changes in watch(jl_path, poll_delay_seconds=0.5):
        current_line_count = sum(1 for _ in open(jl_path))
        if current_line_count > last_line_count:
            with open(jl_path) as f:
                lines = f.readlines()

            new_events = []
            for line in lines[last_line_count:]:
                ev = parse_event(line)
                if ev:
                    new_events.append(ev)

            if new_events:
                renderer.render_session_events(new_events)

            last_line_count = current_line_count


@main.command()
@click.argument("session_id")
def resume(session_id: str):
    """Resume a session by launching Claude Code with --resume."""
    resolved = resolve_session_id(session_id)
    if not resolved:
        console.print(f"[red]Session not found: {session_id}[/red]")
        sys.exit(1)

    console.print(f"[green]Resuming session[/green] {resolved}")
    import subprocess
    result = subprocess.run(
        ["claude", "--resume", resolved],
        cwd=str(Path.home()),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
