# claude-session-tools

Proxy/viewer for Claude Code CLI sessions. Watch, replay, and manage Claude Code sessions from the terminal.

## Install

```bash
cd ~/clawd/projects/claude-session-tools
pip install -e .
```

## Commands

```bash
# List all sessions
claude-session list

# View a session (most recent N events)
claude-session cat <session-id> [-n 100]

# Watch a session live (recent + new events as they arrive)
claude-session watch <session-id>

# Tail new events only (no history)
claude-session tail <session-id>

# Resume a session in Claude Code
claude-session resume <session-id>
```

## Session ID

You can use:
- Full UUID: `b7dd6819-c9fd-4c50-974c-fc986ad7ffbe`
- Short prefix: `b7dd6819`
- Session name: `atenea-saas-interview-ai`
- PID: `52841`

## How it works

- Session metadata: `~/.claude/sessions/*.json`
- Session data: `~/.claude/projects/<project>/<session-id>.jsonl`

The JSONL contains structured events (user messages, assistant responses, tool calls, tool results). The viewer parses and renders these into a terminal UI similar to what Claude Code shows.
