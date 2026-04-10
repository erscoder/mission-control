"""
Renderer for Claude Code session events.
Produces rich terminal output similar to Claude Code's UI.
"""
from __future__ import annotations

import json
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.pretty import Pretty
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

if TYPE_CHECKING:
    from .parser import AssistantMessage, SessionEvent, ToolCall, ToolResult, UserMessage


# ANSI color codes for diffs (matching Claude Code style)
GREEN = "#3fb950"
RED = "#f85149"
BLUE = "#58a6ff"
YELLOW = "#d29922"
PURPLE = "#bc8cff"
GRAY = "#8b949e"


def ts(ts_str: str) -> str:
    """Format ISO timestamp to local time."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return ts_str.split("T")[1][:8] if "T" in ts_str else ts_str


class SessionRenderer:
    """Renders session events to a Rich console."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    # ------------------------------------------------------------------
    # Tool-specific renderers
    # ------------------------------------------------------------------

    def render_tool_call(self, tool: "ToolCall", index: int = 0) -> Panel:
        """Render a single tool call in Claude Code style."""
        name = tool.name
        inp = tool.input_data

        content = ""
        style = "bold cyan"

        if name == "Bash":
            cmd = inp.get("command", inp.get("description", ""))
            cwd = inp.get("cwd", "")
            content = f"$ {cmd}"
            if cwd:
                content += f"\n[dim](cwd: {cwd})[/dim]"
            style = "bold cyan"

        elif name == "Read":
            path = inp.get("file_path", inp.get("path", "?"))
            content = f"[blue]📄 Read[/blue] {path}"
            offset = inp.get("offset", 0)
            limit = inp.get("limit", "")
            if offset or limit:
                content += f" [dim](offset={offset}, limit={limit})[/dim]"

        elif name == "Write" or name == "Edit":
            path = inp.get("file_path", inp.get("path", "?"))
            content = f"[blue]✏️  Write[/blue] {path}"
            if name == "Edit":
                old_text = inp.get("old_string", inp.get("old_text", ""))
                new_text = inp.get("new_string", inp.get("new_text", ""))
                if old_text:
                    content += f"\n\n[red]- {old_text[:200]}[/red]"
                if new_text:
                    content += f"\n[green]+ {new_text[:200]}[/green]"

        elif name == "Glob":
            pattern = inp.get("pattern", "*")
            content = f"[blue]🔍 Glob[/blue] {pattern}"

        elif name == "Grep":
            query = inp.get("query", inp.get("path", "?"))
            path = inp.get("path", ".")
            content = f"[blue]🔍 Grep[/blue] \"{query}\" in {path}"

        elif name == "TodoWrite":
            todos = inp.get("todos", [])
            lines = ["[bold]Tasks:[/bold]"]
            for t in todos:
                status = t.get("status", "pending")
                active = t.get("activeForm", t.get("content", ""))
                content_str = t.get("content", "")
                if status == "completed":
                    lines.append(f"  ✅ {content_str}")
                elif status == "in_progress":
                    lines.append(f"  🔄 {active}")
                else:
                    lines.append(f"  ⬜ {content_str}")
            content = "\n".join(lines)

        elif name == "WebSearch":
            query = inp.get("query", "")
            content = f"[blue]🌐 WebSearch[/blue] {query}"

        elif name == "WebFetch":
            url = inp.get("url", "")
            content = f"[blue]🌐 WebFetch[/blue] {url}"

        elif name == "NotebookWrite":
            path = inp.get("path", "?")
            content = f"[blue]📓 NotebookWrite[/blue] {path}"

        elif name == "Task":
            task_name = inp.get("name", inp.get("prompt", "")[:50])
            content = f"[purple]📋 Task[/purple] {task_name}"

        elif name == "Agent":
            prompt = str(inp.get("prompt", ""))[:100]
            content = f"[purple]🤖 Agent[/purple] {prompt}..."

        else:
            # Generic fallback: show first few keys of input
            keys = list(inp.keys())
            preview = ", ".join(f"{k}={json.dumps(inp[k])[:40]}" for k in keys[:3])
            content = f"[cyan]🔧 {name}[/cyan] ({preview})"

        return Panel(
            content,
            title=f"[bold cyan]{name}[/bold cyan]",
            title_align="left",
            border_style=style,
            padding=(0, 1),
        )

    def render_tool_result(self, tool_use_id: str, result: "ToolResult | str | list") -> Panel:
        """Render a tool result."""
        if isinstance(result, ToolResult):
            content = parse_tool_result_text(result.content)
        elif isinstance(result, str):
            content = result
        else:
            content = parse_tool_result_text(result)

        # Truncate long outputs
        if len(content) > 2000:
            content = content[:2000] + f"\n[dim]... (+{len(content)-2000} chars)[/dim]"

        return Panel(
            content or "[dim](no output)[/dim]",
            title=f"[bold yellow]↩ Result[/bold yellow] [{tool_use_id[:12]}]",
            title_align="left",
            border_style="yellow",
            padding=(0, 1),
        )

    # ------------------------------------------------------------------
    # Message-level renderers
    # ------------------------------------------------------------------

    def render_user_message(self, msg: "UserMessage", index: int) -> Panel:
        """Render a user message."""
        content = msg.content
        if isinstance(content, list):
            content = "\n".join(str(c) for c in content)
        content = str(content)[:500] + ("..." if len(str(content)) > 500 else "")

        time = ts(msg.timestamp)
        return Panel(
            f"[bold green]›[/bold green] {content}",
            title=f"[bold green]User[/bold green] {time}",
            title_align="left",
            border_style="green",
            padding=(0, 1),
        )

    def render_assistant_message(self, msg: "AssistantMessage", index: int) -> list[Panel]:
        """Render an assistant message and all its tool calls."""
        panels = []

        if msg.thinking:
            thinking_text = textwrap.shorten(msg.thinking, width=300, placeholder="...")
            panels.append(Panel(
                f"[dim]{thinking_text}[/dim]",
                title="[dim]Thinking[/dim]",
                title_align="left",
                border_style="dim",
                padding=(0, 1),
            ))

        if msg.text and msg.text.strip():
            panels.append(Panel(
                msg.text.strip(),
                title=f"[bold blue]Claude[/bold blue]",
                title_align="left",
                border_style="blue",
                padding=(0, 1),
            ))

        for i, tool in enumerate(msg.tool_calls):
            panels.append(self.render_tool_call(tool, i))

        return panels

    def render_raw_event(self, event: "SessionEvent") -> Panel:
        """Render an unknown/raw event type."""
        data = event.data
        pretty = Pretty(data, max_length=20, expand_all=True)
        return Panel(
            pretty,
            title=f"[bold dim]Event: {event.event_type}[/bold dim]",
            border_style="dim",
        )

    # ------------------------------------------------------------------
    # Full session rendering
    # ------------------------------------------------------------------

    def render_session_events(self, events: list["SessionEvent"], limit: int = 100):
        """Render a list of session events to the console."""
        from .parser import parse_assistant_message, parse_attachment, parse_user_event

        user_count = 0
        assistant_count = 0

        for i, event in enumerate(events[-limit:]):
            evtype = event.event_type

            # Skip internal/system events
            if evtype in (
                "queue-operation",
                "permission-mode",
                "file-history-snapshot",
                "last-prompt",
                "subagent",
            ):
                continue

            if evtype == "user":
                user_count += 1
                msg = parse_user_event(event.data)
                # Skip empty tool result user messages (those are just acks)
                if msg.content.strip() if isinstance(msg.content, str) else True:
                    panel = self.render_user_message(msg, user_count)
                    self.console.print(panel)

            elif evtype == "assistant":
                assistant_count += 1
                msg = parse_assistant_message(event.data)
                panels = self.render_assistant_message(msg, assistant_count)
                for panel in panels:
                    self.console.print(panel)

            elif evtype == "attachment":
                att = parse_attachment(event.data)
                att_type = att.attachment_type

                if att_type == "skill_listing":
                    content = att.data.get("attachment", {}).get("content", "")
                    if content:
                        self.console.print(Panel(
                            content[:500],
                            title="[bold dim]Skills loaded[/bold dim]",
                            border_style="dim",
                        ))

                elif att_type == "deferred_tools_delta":
                    added = att.data.get("attachment", {}).get("addedNames", [])
                    if added:
                        tools_str = ", ".join(added[:15])
                        if len(added) > 15:
                            tools_str += f" ... (+{len(added)-15} more)"
                        self.console.print(f"[dim]Tools available: {tools_str}[/dim]")

                elif att_type == "mcp_instructions_delta":
                    added = att.data.get("attachment", {}).get("addedNames", [])
                    if added:
                        self.console.print(f"[dim]MCP servers: {', '.join(added[:10])}[/dim]")

                # Skip other attachment types for cleaner output

            else:
                panel = self.render_raw_event(event)
                self.console.print(panel)

            self.console.print()  # spacing


def parse_tool_result_text(content: Any) -> str:
    """Convert tool result content to displayable text."""
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


def render_diff(old_text: str, new_text: str, path: str = "") -> Table:
    """Render a side-by-side or unified diff view."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("+/-", width=3, style="bold")
    table.add_column("Content", style="white")

    for line in old_lines:
        table.add_row("[red]-[/red]", f"[red]{line}[/red]")
    for line in new_lines:
        table.add_row("[green]+[/green]", f"[green]{line}[/green]")

    return table
